import tkinter as tk
from tkinter import ttk, messagebox
import requests
import ast

class FletchingCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OSRS Fletching Cost Calculator")

        # Create a notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=1, fill='both')

        # Add the first calculator tab
        self.add_calculator_tab()

    def add_calculator_tab(self):
        calculator = CalculatorTab(self.notebook)
        self.notebook.add(calculator.frame, text=f"Calculator {len(self.notebook.tabs()) + 1}")
        self.notebook.select(calculator.frame)

class CalculatorTab:
    def __init__(self, notebook):
        self.notebook = notebook
        self.frame = ttk.Frame(self.notebook)

        # Input variables
        self.target_xp = tk.StringVar(value='12277395')
        self.current_xp = tk.StringVar(value='0')
        self.crafts_per_hour = tk.StringVar(value='1800')
        self.quantity_per_craft = tk.StringVar(value='1')  # New quantity per craft variable

        # Lists to hold item data
        self.items = []

        self.create_widgets()

    def create_widgets(self):
        mainframe = ttk.Frame(self.frame, padding="10")
        mainframe.grid(row=0, column=0, sticky="NSEW")

        # Target XP
        ttk.Label(mainframe, text="Target XP:").grid(row=0, column=0, sticky="W")
        ttk.Entry(mainframe, textvariable=self.target_xp).grid(row=0, column=1, sticky="WE")

        # Current XP
        ttk.Label(mainframe, text="Current XP:").grid(row=1, column=0, sticky="W")
        ttk.Entry(mainframe, textvariable=self.current_xp).grid(row=1, column=1, sticky="WE")

        # Crafts per hour
        ttk.Label(mainframe, text="Crafts per Hour:").grid(row=2, column=0, sticky="W")
        ttk.Entry(mainframe, textvariable=self.crafts_per_hour).grid(row=2, column=1, sticky="WE")

        # Quantity per Craft
        ttk.Label(mainframe, text="Quantity per Craft:").grid(row=3, column=0, sticky="W")
        ttk.Entry(mainframe, textvariable=self.quantity_per_craft).grid(row=3, column=1, sticky="WE")

        # Add Item Button
        ttk.Button(mainframe, text="Add Item", command=self.add_item).grid(row=4, column=0, columnspan=2, pady=10)

        # Items Treeview
        columns = ("Item Name", "XP per Craft", "Cost per Craft", "Profit per Craft")
        self.tree = ttk.Treeview(mainframe, columns=columns, show="headings", height=5)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        self.tree.grid(row=5, column=0, columnspan=2, sticky="NSEW")

        # Calculate Button
        ttk.Button(mainframe, text="Calculate", command=self.calculate).grid(row=6, column=0, columnspan=2, pady=10)

        # Results Treeview
        result_columns = ("Item Name", "XP per Hour", "Time Required (hrs)", "Total Cost", "Total Profit")
        self.result_tree = ttk.Treeview(mainframe, columns=result_columns, show="headings", height=8)
        for col in result_columns:
            self.result_tree.heading(col, text=col)
            self.result_tree.column(col, width=140)
        self.result_tree.grid(row=7, column=0, columnspan=2, sticky="NSEW")

        # Scrollbars for the results Treeview
        vsb = ttk.Scrollbar(mainframe, orient="vertical", command=self.result_tree.yview)
        vsb.grid(row=7, column=2, sticky='ns')
        self.result_tree.configure(yscrollcommand=vsb.set)

        # Add New Tab Button
        ttk.Button(mainframe, text="New Calculator Tab", command=self.add_new_tab).grid(row=8, column=0, columnspan=2, pady=10)

        # Create styles for color-coded cells
        self.create_styles()

    def create_styles(self):
        # Configure tags directly on the Treeview widget
        self.result_tree.tag_configure('best_time', background='#C6EFCE')   # Light green
        self.result_tree.tag_configure('worst_time', background='#FFC7CE')  # Light red
        self.result_tree.tag_configure('best_cost', background='#C6EFCE')
        self.result_tree.tag_configure('worst_cost', background='#FFC7CE')
        self.result_tree.tag_configure('best_profit', background='#C6EFCE')
        self.result_tree.tag_configure('worst_profit', background='#FFC7CE')

    def add_new_tab(self):
        # Add a new calculator tab
        app = self.notebook.master
        app.add_calculator_tab()

    def add_item(self):
        add_item_window = tk.Toplevel(self.frame)
        add_item_window.title("Add Item")

        # Input fields
        item_name_var = tk.StringVar()
        xp_per_craft_var = tk.StringVar()
        cost_per_craft_var = tk.StringVar()
        profit_per_craft_var = tk.StringVar()

        ttk.Label(add_item_window, text="Item Name:").grid(row=0, column=0, sticky="W")
        ttk.Entry(add_item_window, textvariable=item_name_var).grid(row=0, column=1, sticky="WE")

        ttk.Label(add_item_window, text="XP per Craft:").grid(row=1, column=0, sticky="W")
        ttk.Entry(add_item_window, textvariable=xp_per_craft_var).grid(row=1, column=1, sticky="WE")

        ttk.Label(add_item_window, text="Cost per Craft:").grid(row=2, column=0, sticky="W")
        ttk.Entry(add_item_window, textvariable=cost_per_craft_var).grid(row=2, column=1, sticky="WE")

        ttk.Label(add_item_window, text="Profit per Craft:").grid(row=3, column=0, sticky="W")
        ttk.Entry(add_item_window, textvariable=profit_per_craft_var).grid(row=3, column=1, sticky="WE")

        # Fetch Price Button
        def fetch_price():
            item_name = item_name_var.get()
            quantity_per_craft = self.quantity_per_craft.get()
            try:
                quantity_per_craft = ast.literal_eval(quantity_per_craft.replace('_', ''))
            except:
                quantity_per_craft = 1
            if item_name:
                price = self.get_osrs_price(item_name)
                if price is not None:
                    total_price = price * quantity_per_craft
                    cost_per_craft_var.set(str(total_price))
                else:
                    messagebox.showerror("Error", f"Price for '{item_name}' not found.")
            else:
                messagebox.showerror("Error", "Item name cannot be empty.")

        ttk.Button(add_item_window, text="Fetch Price", command=fetch_price).grid(row=4, column=0, columnspan=2, pady=5)

        # Add Button
        def add_to_list():
            item_name = item_name_var.get()
            xp_per_craft_input = xp_per_craft_var.get()
            cost_per_craft_input = cost_per_craft_var.get()
            profit_per_craft_input = profit_per_craft_var.get()

            if item_name and xp_per_craft_input and cost_per_craft_input:
                xp_per_craft_list = self.parse_input_list(xp_per_craft_input)
                cost_per_craft_list = self.parse_input_list(cost_per_craft_input)
                profit_per_craft_list = self.parse_input_list(profit_per_craft_input) if profit_per_craft_input else [0]

                for xp_per_craft in xp_per_craft_list:
                    for cost_per_craft in cost_per_craft_list:
                        for profit_per_craft in profit_per_craft_list:
                            self.items.append({
                                "name": item_name,
                                "xp_per_craft": xp_per_craft,
                                "cost_per_craft": cost_per_craft,
                                "profit_per_craft": profit_per_craft
                            })
                            self.tree.insert("", "end", values=(item_name, xp_per_craft, cost_per_craft, profit_per_craft))

                add_item_window.destroy()
            else:
                messagebox.showerror("Error", "Item Name, XP per Craft, and Cost per Craft are required.")

        ttk.Button(add_item_window, text="Add Item", command=add_to_list).grid(row=5, column=0, columnspan=2, pady=5)

    def parse_input_list(self, input_str):
        # Support multiple inputs and simple math expressions
        elements = input_str.split(',')
        result = []
        for elem in elements:
            elem = elem.strip().replace('_', '')
            try:
                # Safely evaluate the expression
                value = ast.literal_eval(elem)
                result.append(value)
            except Exception as e:
                messagebox.showerror("Error", f"Invalid input: {elem}")
                return []
        return result

    def calculate(self):
        # Clear previous results
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        try:
            target_xp = ast.literal_eval(self.target_xp.get().replace('_', ''))
            current_xp = ast.literal_eval(self.current_xp.get().replace('_', ''))
            crafts_per_hour = ast.literal_eval(self.crafts_per_hour.get().replace('_', ''))
            quantity_per_craft = ast.literal_eval(self.quantity_per_craft.get().replace('_', ''))
        except Exception as e:
            messagebox.showerror("Error", "Invalid input in one of the fields.")
            return

        xp_needed = target_xp - current_xp

        results = []

        for item in self.items:
            xp_per_craft = item["xp_per_craft"]
            cost_per_craft = item["cost_per_craft"]
            profit_per_craft = item.get("profit_per_craft", 0)

            crafts_needed = xp_needed / xp_per_craft
            xp_per_hour = crafts_per_hour * xp_per_craft
            time_required = xp_needed / xp_per_hour
            total_cost = crafts_needed * cost_per_craft
            total_profit = crafts_needed * profit_per_craft

            results.append({
                "name": item["name"],
                "xp_per_hour": xp_per_hour,
                "time_required": time_required,
                "total_cost": total_cost,
                "total_profit": total_profit
            })

        # Determine best and worst options for each metric
        metrics = {
            'time_required': {'best': min, 'worst': max},
            'total_cost': {'best': min, 'worst': max},
            'total_profit': {'best': max, 'worst': min},
        }

        best_worst_values = {}
        for metric, funcs in metrics.items():
            best_value = funcs['best'](results, key=lambda x: x[metric])[metric]
            worst_value = funcs['worst'](results, key=lambda x: x[metric])[metric]
            best_worst_values[metric] = {'best': best_value, 'worst': worst_value}

        for res in results:
            tags = ['', '', '', '', '']  # Tags for each cell

            # Check for best and worst in 'Time Required'
            if res['time_required'] == best_worst_values['time_required']['best']:
                tags[2] = 'best_time'
            elif res['time_required'] == best_worst_values['time_required']['worst']:
                tags[2] = 'worst_time'

            # Check for best and worst in 'Total Cost'
            if res['total_cost'] == best_worst_values['total_cost']['best']:
                tags[3] = 'best_cost'
            elif res['total_cost'] == best_worst_values['total_cost']['worst']:
                tags[3] = 'worst_cost'

            # Check for best and worst in 'Total Profit'
            if res['total_profit'] == best_worst_values['total_profit']['best']:
                tags[4] = 'best_profit'
            elif res['total_profit'] == best_worst_values['total_profit']['worst']:
                tags[4] = 'worst_profit'

            # Insert the item with tags for each cell
            self.result_tree.insert("", "end", values=(
                res["name"],
                self.format_number(res['xp_per_hour']),
                self.format_number(res['time_required']),
                self.format_number(res['total_cost']),
                self.format_number(res['total_profit'])
            ))

            # Apply tags to specific cells
            item_id = self.result_tree.get_children()[-1]
            for col_index, tag in enumerate(tags):
                if tag:
                    self.result_tree.tag_configure(tag, background=self.result_tree.tag_cget(tag, 'background'))
                    self.result_tree.set(item_id, column=col_index, value=self.result_tree.item(item_id)['values'][col_index], tags=(tag,))

    def format_number(self, num):
        # Format numbers using k, m, b, etc.
        num = float(num)
        abs_num = abs(num)
        if abs_num >= 1_000_000_000:
            return f"{num/1_000_000_000:.2f}b"
        elif abs_num >= 1_000_000:
            return f"{num/1_000_000:.2f}m"
        elif abs_num >= 1_000:
            return f"{num/1_000:.2f}k"
        else:
            return f"{num:.2f}"

    def get_osrs_price(self, item_name):
        # Fetch item ID from the OSRS Wiki Mapping API
        mapping_url = "https://prices.runescape.wiki/api/v1/osrs/mapping"
        try:
            mapping_response = requests.get(mapping_url)
            mapping_data = mapping_response.json()
            item_id = None
            for item in mapping_data:
                if item["name"].lower() == item_name.lower():
                    item_id = item["id"]
                    break
            if item_id is None:
                return None

            # Fetch latest price using the item ID
            prices_url = f"https://prices.runescape.wiki/api/v1/osrs/latest"
            prices_response = requests.get(prices_url)
            prices_data = prices_response.json()
            item_prices = prices_data["data"].get(str(item_id))
            if item_prices:
                price = item_prices["high"] or item_prices["low"]
                return price
            else:
                return None
        except Exception as e:
            print(f"Error fetching price: {e}")
            return None

def main():
    root = tk.Tk()
    app = FletchingCalculatorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
