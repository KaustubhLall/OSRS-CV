import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext, messagebox
import threading
import queue
import time
import datetime
import yaml
import json
import os
import logging
from functools import wraps
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
import requests
from threading import Lock

# -------------------- Config Class -------------------- #

class Config:
    def __init__(self, config_path='config.yaml'):
        self.config_path = config_path
        self.default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 5000,
            },
            'security': {
                'bearer_token': '',
            },
            'logging': {
                'level': 'DEBUG',
                'file': 'osrs_events.log',
            },
            'database': {
                'uri': 'sqlite:///events.db',
            },
            'api': {
                'prefix': '/api',
            },
            'mappings': {
                'item_file': 'items.json',
                'npc_file': 'npcs.json',
            }
        }
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                loaded_config = yaml.safe_load(f)
            # Update default config with loaded config
            self.update_dict(self.default_config, loaded_config)
            config = self.default_config
        else:
            config = self.default_config.copy()
        return config

    def save_config(self):
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config, f)

    def update_dict(self, default, update):
        for k, v in update.items():
            if isinstance(v, dict) and k in default:
                self.update_dict(default[k], v)
            else:
                default[k] = v
        return default

# -------------------- Logger Setup -------------------- #

class Logger:
    def __init__(self, config):
        self.log_level = getattr(logging, config['logging']['level'].upper(), logging.DEBUG)
        self.log_file = config['logging']['file']
        self.logger = logging.getLogger('OSRSEvents')
        self.logger.setLevel(self.log_level)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

        # Remove existing handlers to prevent duplicate logs
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # Stream handler
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(self.log_level)
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)

        # File handler
        if self.log_file:
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(self.log_level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def get_logger(self):
        return self.logger

# -------------------- Database Setup -------------------- #

Base = declarative_base()

class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False)
    data = Column(JSON, nullable=False)
    timestamp = Column(String(50), nullable=False)
    received_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

class Database:
    def __init__(self, config, logger):
        self.uri = config['database']['uri']
        self.logger = logger
        self.engine = create_engine(self.uri, echo=False, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.lock = Lock()

    def add_event(self, event_type, data, timestamp):
        with self.lock:
            session = self.Session()
            try:
                event = Event(event_type=event_type, data=data, timestamp=timestamp)
                session.add(event)
                session.commit()
                event_id = event.id
                self.logger.info(f"Event '{event_type}' saved to database with ID {event_id}.")
                return event_id
            except Exception as e:
                session.rollback()
                self.logger.error(f"Error saving event to database: {e}")
                return None
            finally:
                session.close()

    def get_events(self, limit=100):
        session = self.Session()
        try:
            events = session.query(Event).order_by(Event.received_at.desc()).limit(limit).all()
            return events
        except Exception as e:
            self.logger.error(f"Error fetching events from database: {e}")
            return []
        finally:
            session.close()

    def get_event_by_id(self, event_id):
        session = self.Session()
        try:
            event = session.get(Event, event_id)
            return event
        except Exception as e:
            self.logger.error(f"Error fetching event ID {event_id}: {e}")
            return None
        finally:
            session.close()

# -------------------- Data Fetcher -------------------- #

class ItemCache:
    def __init__(self, logger, config, cache_duration=3600):
        self.config = config
        self.item_mapping = {}
        self.npc_mapping = {}
        self.price_data = {}
        self.cache_duration = cache_duration  # seconds
        self.last_price_fetch_time = 0
        self.lock = threading.Lock()
        self.logger = logger

        # Load mappings synchronously to ensure availability before processing events
        self.load_mappings()

        # Start background thread to fetch price data periodically
        self.price_thread = threading.Thread(target=self.periodic_price_fetch, daemon=True)
        self.price_thread.start()

    def load_mappings(self):
        # Load item mappings
        item_file = self.get_config_path('item_file')
        if os.path.exists(item_file):
            try:
                with open(item_file, 'r') as f:
                    item_data = json.load(f)
                for item in item_data:
                    item_id = int(item['id'])
                    item_name = item['name']
                    self.item_mapping[item_id] = item_name
                self.logger.info(f"Loaded item mapping from {item_file}")
            except Exception as e:
                self.logger.error(f"Error loading item mapping from {item_file}: {e}")
                self.fetch_item_mapping()
        else:
            self.fetch_item_mapping()

        # Load NPC mappings
        npc_file = self.get_config_path('npc_file')
        if os.path.exists(npc_file):
            try:
                with open(npc_file, 'r') as f:
                    npc_data = json.load(f)
                for npc in npc_data:
                    npc_id = int(npc['id'])
                    npc_name = npc['name']
                    self.npc_mapping[npc_id] = npc_name
                self.logger.info(f"Loaded NPC mapping from {npc_file}")
            except Exception as e:
                self.logger.error(f"Error loading NPC mapping from {npc_file}: {e}")
                self.load_default_npc_mapping()
        else:
            self.load_default_npc_mapping()

    def load_default_npc_mapping(self):
        # Default minimal NPC mapping
        self.npc_mapping = {
            44: 'Goblin',
            299: 'Black Knight',
            # Add more NPCs as needed
        }
        self.logger.info("Default NPC mapping loaded.")

    def get_config_path(self, filename_key):
        return self.config['mappings'].get(filename_key, filename_key)

    def fetch_item_mapping(self):
        url = 'https://prices.runescape.wiki/api/v1/osrs/mapping'
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            with open(self.get_config_path('item_file'), 'w') as f:
                json.dump(data, f)
            for item in data:
                item_id = int(item['id'])
                item_name = item['name']
                self.item_mapping[item_id] = item_name
            self.logger.info("Fetched and saved item mapping from OSRS API")
        except Exception as e:
            self.logger.error(f"Error fetching item mapping from OSRS API: {e}")

    def fetch_price_data(self):
        url = 'https://prices.runescape.wiki/api/v1/osrs/latest'
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            with self.lock:
                self.price_data = data.get('data', {})
                self.last_price_fetch_time = time.time()
            self.logger.info("Fetched latest price data")
        except Exception as e:
            self.logger.error(f"Error fetching latest price data: {e}")

    def periodic_price_fetch(self):
        while True:
            self.fetch_price_data()
            time.sleep(self.cache_duration)  # Fetch prices every cache_duration seconds

    def get_item_info(self, item_id):
        item_id = int(item_id)
        with self.lock:
            current_time = time.time()
            if current_time - self.last_price_fetch_time > self.cache_duration:
                # Trigger immediate price fetch if cache expired
                self.fetch_price_data()
            item_name = self.item_mapping.get(item_id, f"Item {item_id}")
            price_entry = self.price_data.get(str(item_id), {})
            high_price = price_entry.get('high')
            low_price = price_entry.get('low')
            item_price = high_price if high_price else low_price
            item_data = {
                'itemName': item_name,
                'itemPrice': item_price,
                'itemPriceFormatted': format_number(item_price),
                'last_price_fetched': int(self.last_price_fetch_time)
            }
            return item_data

    def get_npc_name(self, npc_id):
        return self.npc_mapping.get(npc_id, f"NPC {npc_id}")

def format_number(value):
    if value is None:
        return "N/A"
    try:
        num = float(value)
        if num >= 1_000_000_000_000:
            return f"{num/1_000_000_000_000:.2f}T"
        elif num >= 1_000_000_000:
            return f"{num/1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"{num/1_000_000:.2f}M"
        elif num >= 1_000:
            return f"{num/1_000:.2f}k"
        else:
            return str(int(num))
    except (ValueError, TypeError):
        return str(value)

# -------------------- Request Counter -------------------- #

class RequestCounter:
    def __init__(self):
        self.count = 0
        self.lock = Lock()

    def increment(self):
        with self.lock:
            self.count += 1
            return self.count

    def decrement(self):
        with self.lock:
            self.count -= 1
            return self.count

    def get_count(self):
        with self.lock:
            return self.count

# -------------------- Flask Server Setup -------------------- #

from flask import Flask, request, jsonify

def create_app(config, logger, database, item_cache, event_queue, request_counter):
    app = Flask(__name__)
    api_prefix = config['api']['prefix']
    bearer_token = config['security']['bearer_token']

    def require_bearer_token(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = bearer_token
            if token:
                auth_header = request.headers.get('Authorization', '')
                if not auth_header.startswith('Bearer '):
                    logger.warning("Missing or malformed Authorization header")
                    return jsonify({'error': 'Unauthorized'}), 401
                parts = auth_header.split()
                if len(parts) != 2 or parts[0] != 'Bearer':
                    logger.warning("Invalid Bearer token format")
                    return jsonify({'error': 'Unauthorized'}), 401
                received_token = parts[1]
                if received_token != token:
                    logger.warning("Invalid Bearer token")
                    return jsonify({'error': 'Unauthorized'}), 401
            return f(*args, **kwargs)
        return decorated

    def validate_json(required_fields):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not request.is_json:
                    logger.error("Request content type is not application/json")
                    return jsonify({'error': 'Invalid Content Type'}), 400
                data = request.get_json()
                missing = [field for field in required_fields if field not in data]
                if missing:
                    logger.error(f"Missing fields in JSON: {missing}")
                    return jsonify({'error': f'Missing fields: {missing}'}), 400
                return f(data, *args, **kwargs)
            return decorated_function
        return decorator

    supported_endpoints = {
        'npc_kill': '/npc_kill/',
        'level_change': '/level_change/',
        'bank': '/bank/',
        'equipped_items': '/equipped_items/',
        'inventory_items': '/inventory_items/',
        'login_state': '/login_state/',
        'quest_change': '/quest_change/'
    }

    event_type_mapping = {
        'npc_kill': 'NpcKillNotification',
        'level_change': 'LevelChangeNotification',
        'bank': 'BankNotification',
        'equipped_items': 'EquipSlotsNotification',
        'inventory_items': 'InventorySlotsNotification',
        'login_state': 'LoginNotification',
        'quest_change': 'QuestChangeNotification'
    }

    def process_event(event_type, data):
        logger.info(f"Received {event_type} event")
        timestamp = data.get('timestamp', datetime.datetime.now().isoformat())
        data['timestamp'] = timestamp
        event_id = database.add_event(event_type, data, timestamp)
        if event_id:
            event_queue.put({'event_type': event_type, 'data': data, 'timestamp': timestamp, 'id': event_id})

    def create_handler(event_type_inner, full_endpoint_inner):
        @app.route(full_endpoint_inner, methods=['POST'], endpoint=f"handler_{event_type_inner}")
        @require_bearer_token
        @validate_json(['data', 'timestamp'])
        def handler(data, event_type_inner=event_type_inner):
            request_counter.increment()
            try:
                process_event(event_type_inner, data)
                response = jsonify({'status': 'success'}), 200
            except Exception as e:
                logger.error(f"Error processing event {event_type_inner}: {e}")
                response = jsonify({'status': 'error', 'message': str(e)}), 500
            finally:
                request_counter.decrement()
            return response

    for event_type_key, endpoint in supported_endpoints.items():
        event_type = event_type_mapping.get(event_type_key)
        if not event_type:
            logger.warning(f"No event type mapping found for key '{event_type_key}'. Skipping endpoint '{endpoint}'.")
            continue
        full_endpoint = f"{api_prefix}{endpoint}"
        create_handler(event_type, full_endpoint)
        logger.debug(f"Created handler for event type '{event_type}' at endpoint '{full_endpoint}'")

    return app

def run_server(app, host, port):
    app.run(host=host, port=port, use_reloader=False, threaded=True)

class ServerThread(threading.Thread):
    def __init__(self, app, host, port, logger):
        threading.Thread.__init__(self)
        self.app = app
        self.host = host
        self.port = port
        self.logger = logger
        self.daemon = True  # Allow thread to be killed when main thread exits

    def run(self):
        try:
            self.logger.info(f"Starting Flask server on {self.host}:{self.port}")
            run_server(self.app, self.host, self.port)
        except Exception as e:
            self.logger.error(f"Server error: {e}")

# -------------------- Main Application -------------------- #

class App:
    def __init__(self, root, request_counter):
        self.root = root
        self.root.title("OSRS Events Dashboard")
        self.root.geometry("1000x700")

        self.request_counter = request_counter

        self.config = Config()
        self.logger = Logger(self.config.config).get_logger()
        self.database = Database(self.config.config, self.logger)
        self.event_queue = queue.Queue()

        self.item_cache = ItemCache(self.logger, self.config.config)

        # Set up the UI
        self.setup_ui()

        # Start the server
        self.start_server()

        # Start updating the UI
        self.update_ui()

    def setup_ui(self):
        # Active requests label
        self.active_requests_label = ttk.Label(self.root, text="Active Requests: 0")
        self.active_requests_label.pack(pady=5)

        # PanedWindow for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True)

        # Config tab
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text='Config')
        self.setup_config_tab()

        # Events tab
        self.events_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.events_frame, text='Events')
        self.setup_events_tab()

        # Logs tab
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text='Logs')
        self.setup_logs_tab()

    def setup_config_tab(self):
        # Display config options
        self.config_text = scrolledtext.ScrolledText(self.config_frame, wrap='word')
        self.config_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.load_config()

        # Save button
        self.save_button = ttk.Button(self.config_frame, text='Save Config', command=self.save_config)
        self.save_button.pack(pady=5)

    def load_config(self):
        config_str = yaml.dump(self.config.config)
        self.config_text.delete('1.0', tk.END)
        self.config_text.insert(tk.END, config_str)

    def save_config(self):
        config_str = self.config_text.get('1.0', tk.END)
        try:
            config = yaml.safe_load(config_str)
            if not isinstance(config, dict):
                raise ValueError("Configuration must be a valid YAML dictionary.")
            self.config.config = config
            self.config.save_config()
            self.logger.info("Configuration saved.")
            messagebox.showinfo("Config", "Configuration saved successfully.")
            # Optionally, you can implement restarting the server or other components if needed
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            messagebox.showerror("Error", f"Error saving config: {e}")

    def setup_events_tab(self):
        # Create a PanedWindow for resizable panes
        self.paned_window = ttk.PanedWindow(self.events_frame, orient=tk.VERTICAL)
        self.paned_window.pack(fill='both', expand=True, padx=5, pady=5)

        # Treeview to display events
        self.events_tree = ttk.Treeview(self.paned_window, columns=('Event Type', 'Timestamp', 'Received At'), show='headings')
        self.events_tree.heading('Event Type', text='Event Type')
        self.events_tree.heading('Timestamp', text='Timestamp')
        self.events_tree.heading('Received At', text='Received At')
        self.events_tree.column('Event Type', width=200, stretch=True)
        self.events_tree.column('Timestamp', width=200, stretch=True)
        self.events_tree.column('Received At', width=200, stretch=True)
        self.paned_window.add(self.events_tree)

        # Lower pane with event data tree and text view
        self.lower_pane = ttk.PanedWindow(self.paned_window, orient=tk.HORIZONTAL)
        self.paned_window.add(self.lower_pane)

        # Left frame for tree view
        self.tree_frame = ttk.Frame(self.lower_pane)
        self.lower_pane.add(self.tree_frame, weight=1)

        # Buttons for expand/collapse
        self.button_frame = ttk.Frame(self.tree_frame)
        self.button_frame.pack(side=tk.TOP, fill=tk.X)

        self.expand_button = ttk.Button(self.button_frame, text='Expand All', command=self.expand_all)
        self.expand_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.collapse_button = ttk.Button(self.button_frame, text='Collapse All', command=self.collapse_all)
        self.collapse_button.pack(side=tk.LEFT, padx=5, pady=5)

        # event_data_tree
        self.event_data_tree = ttk.Treeview(self.tree_frame)
        self.event_data_tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Right frame for text view
        self.text_frame = ttk.Frame(self.lower_pane)
        self.lower_pane.add(self.text_frame, weight=1)

        # Copy JSON button
        self.copy_button = ttk.Button(self.text_frame, text='Copy JSON', command=self.copy_json)
        self.copy_button.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # event_data_text
        self.event_data_text = scrolledtext.ScrolledText(self.text_frame, wrap='word', state='disabled')
        self.event_data_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Bind selection event
        self.events_tree.bind('<<TreeviewSelect>>', self.on_event_select)

        # Load initial events
        self.load_events()

    def expand_all(self):
        self.expand_tree(self.event_data_tree)

    def expand_tree(self, tree, item=''):
        tree.item(item, open=True)
        children = tree.get_children(item)
        for child in children:
            self.expand_tree(tree, child)

    def collapse_all(self):
        self.collapse_tree(self.event_data_tree)

    def collapse_tree(self, tree, item=''):
        tree.item(item, open=False)
        children = tree.get_children(item)
        for child in children:
            self.collapse_tree(tree, child)

    def copy_json(self):
        json_text = self.event_data_text.get('1.0', tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(json_text)
        messagebox.showinfo("Copy JSON", "JSON data copied to clipboard.")

    def load_events(self):
        events = self.database.get_events()
        for event in reversed(events):  # Reverse to show oldest first
            # Parse timestamp
            try:
                timestamp_dt = datetime.datetime.fromisoformat(event.timestamp)
                timestamp_str = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                timestamp_str = event.timestamp
            received_at_str = event.received_at.strftime('%Y-%m-%d %H:%M:%S')
            self.events_tree.insert('', 'end', iid=event.id, values=(event.event_type, timestamp_str, received_at_str))

    def on_event_select(self, event):
        selected_item = self.events_tree.selection()
        if selected_item:
            event_id = int(selected_item[0])
            event_record = self.database.get_event_by_id(event_id)
            if event_record:
                # Clear the tree
                self.clear_tree(self.event_data_tree)
                # Display the JSON data in the tree
                data = event_record.data
                self.display_json_in_tree(self.event_data_tree, '', data)
                # Display the JSON data in the text widget
                data_str = json.dumps(data, indent=2)
                self.event_data_text.configure(state='normal')
                self.event_data_text.delete('1.0', tk.END)
                self.event_data_text.insert(tk.END, data_str)
                self.event_data_text.configure(state='disabled')

    def clear_tree(self, tree):
        tree.delete(*tree.get_children())

    def display_json_in_tree(self, tree, parent, json_data):
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                if isinstance(value, (dict, list)):
                    node_id = tree.insert(parent, 'end', text=str(key), open=False)
                    self.display_json_in_tree(tree, node_id, value)
                else:
                    node_text = f"{key}: {value}"
                    tree.insert(parent, 'end', text=node_text)
        elif isinstance(json_data, list):
            for index, item in enumerate(json_data):
                if isinstance(item, (dict, list)):
                    node_id = tree.insert(parent, 'end', text=f"[{index}]", open=False)
                    self.display_json_in_tree(tree, node_id, item)
                else:
                    node_text = f"[{index}]: {item}"
                    tree.insert(parent, 'end', text=node_text)
        else:
            tree.insert(parent, 'end', text=str(json_data))

    def setup_logs_tab(self):
        self.log_text = scrolledtext.ScrolledText(self.logs_frame, wrap='word', state='disabled')
        self.log_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.log_queue = queue.Queue()
        self.setup_logger()

    def setup_logger(self):
        # Set up a logging handler that writes to the log_text widget
        class QueueHandler(logging.Handler):
            def __init__(self, log_queue):
                super().__init__()
                self.log_queue = log_queue

            def emit(self, record):
                log_entry = self.format(record)
                self.log_queue.put(log_entry)

        handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def update_ui(self):
        # Check for new events in the queue
        try:
            while True:
                event_data = self.event_queue.get_nowait()
                event_type = event_data.get('event_type')
                timestamp = event_data.get('timestamp')
                received_at = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                event_id = event_data.get('id')

                # Ensure timestamp is a string
                if not isinstance(timestamp, str):
                    if timestamp is None:
                        self.logger.warning(f"Event ID {event_id} has no timestamp. Using current time.")
                        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    else:
                        self.logger.warning(
                            f"Timestamp for Event ID {event_id} is not a string: {timestamp} (type: {type(timestamp)}). Converting to string.")
                        timestamp = str(timestamp)

                # Format timestamp
                try:
                    timestamp_dt = datetime.datetime.fromisoformat(timestamp)
                    timestamp_str = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    self.logger.error(
                        f"Invalid timestamp format for Event ID {event_id}: {timestamp}. Using original value.")
                    timestamp_str = timestamp

                # Insert the event into the Treeview if not already present
                if not self.events_tree.exists(event_id):
                    self.events_tree.insert('', 'end', iid=event_id, values=(event_type, timestamp_str, received_at))
        except queue.Empty:
            pass

        # Update logs
        try:
            while True:
                log_message = self.log_queue.get_nowait()
                self.log_text.configure(state='normal')
                self.log_text.insert(tk.END, log_message + '\n')
                self.log_text.see(tk.END)
                self.log_text.configure(state='disabled')
        except queue.Empty:
            pass

        # Update active requests label
        active_requests = self.request_counter.get_count()
        self.active_requests_label.config(text=f"Active Requests: {active_requests}")

        # Schedule the next update
        self.root.after(100, self.update_ui)

    def start_server(self):
        # Create the Flask app
        app = create_app(self.config.config, self.logger, self.database, self.item_cache, self.event_queue, self.request_counter)
        # Start the server in a separate thread
        host = self.config.config['server']['host']
        port = self.config.config['server']['port']
        self.server_thread = ServerThread(app, host, port, self.logger)
        self.server_thread.start()
        self.logger.info(f"Server started on {host}:{port}")

# -------------------- Run the Application -------------------- #

if __name__ == '__main__':
    root = tk.Tk()
    request_counter = RequestCounter()
    app = App(root, request_counter)
    root.mainloop()
