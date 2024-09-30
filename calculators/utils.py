import requests
import difflib
import json
import time
import logging

# Configure logging
logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)

# Constants for OSRS Wiki APIs
MAPPING_API_URL = "https://prices.runescape.wiki/api/v1/osrs/mapping"
PRICES_API_URL = "https://prices.runescape.wiki/api/v1/osrs/latest"

# Cache for mapping data
mapping_cache = None

# Dictionary for known problematic item names (normalized)
ITEM_NAME_CORRECTIONS = {
    "onyx dragon bolts": "Onyx dragon bolts",
    "onyx-tipped runite bolts": "Onyx bolts",
    "amethyst-tipped broad bolts": "Amethyst-tipped broad bolts",
    "barbed-tipped bronze bolts": "Barbed bolts",
    "diamond-tipped adamant bolts": "Diamond adamant bolts",
    "sapphire-tipped mithril bolts": "Sapphire bolts",
    # Add more corrections as needed
}

# Dictionary for valid gem and bolt combinations
GEM_BOLT_COMBINATIONS = {
    "Amethyst": "Amethyst-tipped broad bolts",
    "Barbed": "Barbed bronze bolts",
    "Diamond": "Diamond adamant bolts",
    "Dragonstone": "Dragonstone-tipped runite bolts",
    "Emerald": "Emerald-tipped mithril bolts",
    "Jade": "Jade-tipped blurite bolts",
    "Onyx": "Onyx-tipped runite bolts",
    "Opal": "Opal-tipped bronze bolts",
    "Pearl": "Pearl-tipped iron bolts",
    "Red topaz": "Red topaz-tipped steel bolts",
    "Ruby": "Ruby-tipped adamant bolts",
    "Sapphire": "Sapphire mithril bolts",
    # Add more gems and their corresponding bolt types as needed
}

# Hardcoded crafting recipes (Assuming experience per craft remains constant)
CRAFTING_RECIPES = {
    "Amethyst-tipped broad bolts": {"exp_per_craft": 10.6},
    "Barbed bronze bolts": {"exp_per_craft": 9.5},
    "Diamond adamant bolts": {"exp_per_craft": 7},
    "Dragonstone-tipped runite bolts": {"exp_per_craft": 8.2},
    "Emerald-tipped mithril bolts": {"exp_per_craft": 5.5},
    "Jade-tipped blurite bolts": {"exp_per_craft": 2.4},
    "Onyx-tipped runite bolts": {"exp_per_craft": 9.4},
    "Opal-tipped bronze bolts": {"exp_per_craft": 1.6},
    "Pearl-tipped iron bolts": {"exp_per_craft": 3.2},
    "Red topaz-tipped steel bolts": {"exp_per_craft": 3.9},
    "Ruby-tipped adamant bolts": {"exp_per_craft": 6.3},
    "Sapphire mithril bolts": {"exp_per_craft": 4.7},
    # Add more recipes as needed
}

def fetch_mapping_data():
    """
    Fetches and caches the mapping data from the OSRS Wiki Mapping API.

    Returns:
        list: A list of item dictionaries with 'id' and 'name'.
    """
    global mapping_cache
    if mapping_cache is None:
        try:
            logger.info("Fetching mapping data from OSRS Wiki...")
            response = requests.get(MAPPING_API_URL, timeout=10)
            response.raise_for_status()
            mapping_cache = response.json()  # Assuming the response is a list
            logger.info(f"Mapping data fetched successfully. Total items: {len(mapping_cache)}")
        except requests.RequestException as e:
            logger.error(f"Error fetching mapping data: {e}")
            mapping_cache = []
    return mapping_cache

def normalize_name(name):
    """
    Normalizes the item name by converting to lowercase and stripping extra spaces.

    Parameters:
        name (str): The item name to normalize.

    Returns:
        str: Normalized item name.
    """
    return ' '.join(name.lower().strip().split())

def get_item_id(item_name, mapping_data):
    """
    Maps an item name to its corresponding item ID using the mapping data.

    Parameters:
        item_name (str): The name of the item to find.
        mapping_data (list): The data obtained from the OSRS Wiki Mapping API.

    Returns:
        int or None: The item ID if found; otherwise, None.
    """
    # Normalize the input item name
    normalized_input = normalize_name(item_name)

    # Apply corrections if applicable
    corrected_name = ITEM_NAME_CORRECTIONS.get(normalized_input, normalized_input)

    # Attempt exact match
    for item in mapping_data:
        item_normalized = normalize_name(item['name'])
        if item_normalized == corrected_name.lower():
            logger.debug(f"Exact match found: '{item['name']}' with ID {item['id']}")
            return item['id']

    # If exact match not found, use approximate matching
    all_names = [item['name'] for item in mapping_data]
    close_matches = difflib.get_close_matches(corrected_name, all_names, n=1, cutoff=0.8)
    if close_matches:
        matched_name = close_matches[0]
        for item in mapping_data:
            if item['name'] == matched_name:
                logger.debug(f"Approximate match found: '{matched_name}' with ID {item['id']}")
                return item['id']

    # If no match found
    logger.warning(f"No match found for item name: '{item_name}' (normalized: '{normalized_input}')")
    return None

def get_osrs_price(item_name):
    """
    Fetches the latest price for a given item from the OSRS Wiki Prices API.

    Parameters:
        item_name (str): The name of the item whose price is to be fetched.

    Returns:
        int or None: The price in gp if found; otherwise, None.
    """
    mapping_data = fetch_mapping_data()
    if not mapping_data:
        logger.error("Mapping data is unavailable. Cannot fetch prices.")
        return None

    item_id = get_item_id(item_name, mapping_data)
    if item_id is None:
        logger.error(f"Item ID not found for item: '{item_name}'")
        return None

    # Attempt to fetch price with retries
    retries = 3
    for attempt in range(retries):
        try:
            logger.info(f"Fetching price for item ID {item_id} ('{item_name}')... Attempt {attempt + 1}")
            response = requests.get(PRICES_API_URL, timeout=10)
            response.raise_for_status()
            price_data = response.json().get('data', {})
            item_key = str(item_id)
            if item_key in price_data:
                item_prices = price_data[item_key]
                price = item_prices.get('high') or item_prices.get('low')
                if price is not None:
                    logger.info(f"Price for '{item_name}': {price} gp")
                    return price
                else:
                    logger.warning(f"No 'high' or 'low' price available for item ID: {item_id}")
                    return None
            else:
                logger.warning(f"Price data not found for item ID: {item_id}")
                return None
        except requests.RequestException as e:
            logger.error(f"Error fetching price data: {e}. Retry {attempt + 1}/{retries}")
            time.sleep(2)  # Wait before retrying
    logger.error(f"Failed to fetch price for item ID {item_id} after {retries} attempts.")
    return None

def add_gem_tipped_bolts(gem):
    """
    Constructs the names for bolt tips and finished bolts based on the selected gem.
    Fetches their prices and calculates cost and profit.

    Parameters:
        gem (str): The name of the gem.

    Returns:
        dict or None: A dictionary with calculated costs and profits, or None if failed.
    """
    if gem not in GEM_BOLT_COMBINATIONS:
        logger.error(f"Invalid gem selected: '{gem}'. Available gems: {list(GEM_BOLT_COMBINATIONS.keys())}")
        return None

    bolt_name = GEM_BOLT_COMBINATIONS[gem]
    recipe = CRAFTING_RECIPES.get(bolt_name)
    if not recipe:
        logger.error(f"No crafting recipe found for: '{bolt_name}'")
        return None

    # Fetch prices
    # Fetch the base bolt price if applicable
    # Assuming base bolts are part of the bolt name; adjust if there's a separate base item
    # For example, "Amethyst-tipped broad bolts" implies using "Broad bolts" as the base
    # Adjust accordingly based on actual crafting requirements

    # For simplicity, assuming the base bolt is included in the cost as a separate item
    # If there's no separate base bolt, set base_bolt_price to 0
    # You may need to adjust this based on the actual crafting process

    # Example: Assuming "Broad bolts" are the base bolts
    base_bolt_name = "Broad bolts"
    base_bolt_price = get_osrs_price(base_bolt_name)
    if base_bolt_price is None:
        logger.error(f"Base bolt price not found for: '{base_bolt_name}'")
        return None

    # Fetch the gem (bolt tip) price
    bolt_tip_price = get_osrs_price(gem)
    if bolt_tip_price is None:
        logger.error(f"Gem price not found for: '{gem}'")
        return None

    # Fetch the finished bolt price
    finished_bolt_price = get_osrs_price(bolt_name)
    if finished_bolt_price is None:
        logger.error(f"Finished bolt price not found for: '{bolt_name}'")
        return None

    # Calculate costs
    cost_per_craft = base_bolt_price + bolt_tip_price
    profit_per_craft = finished_bolt_price - cost_per_craft

    return {
        "bolt_name": bolt_name,
        "base_bolt_price": base_bolt_price,
        "bolt_tip_price": bolt_tip_price,
        "finished_bolt_price": finished_bolt_price,
        "cost_per_craft": cost_per_craft,
        "profit_per_craft": profit_per_craft,
        "exp_per_craft": recipe["exp_per_craft"]
    }

def test_get_item_id(mapping_data):
    """
    Tests the get_item_id function with various test cases.
    """
    test_cases = [
        "Onyx bolts",
        "Onyx dragon bolts",
        "Onyx bolts (e)",
        "Amethyst-tipped broad bolts",
        "Barbed-tipped bronze bolts",
        "Diamond-tipped adamant bolts",
        "Sapphire-tipped mithril bolts",
        "Nonexistent Item"
    ]

    print("Testing get_item_id function:")
    for name in test_cases:
        item_id = get_item_id(name, mapping_data)
        print(f"Item Name: '{name}' => Item ID: {item_id}")
    print("\n")

def test_get_osrs_price():
    """
    Tests the get_osrs_price function with various test cases.
    """
    test_items = [
        "Onyx bolts",
        "Onyx dragon bolts",
        "Onyx bolts (e)",
        "Amethyst-tipped broad bolts",
        "Barbed-tipped bronze bolts",
        "Diamond-tipped adamant bolts",
        "Sapphire-tipped mithril bolts",
        "Nonexistent Item"
    ]

    print("Testing get_osrs_price function:")
    for item in test_items:
        price = get_osrs_price(item)
        print(f"Item Name: '{item}' => Price: {price} gp")
    print("\n")

def test_add_gem_tipped_bolts():
    """
    Tests the add_gem_tipped_bolts function with various gems.
    """
    test_gems = [
        "Amethyst",
        "Onyx",
        "Ruby",
        "Nonexistent Gem",
        "Sapphire"
    ]

    print("Testing add_gem_tipped_bolts function:")
    for gem in test_gems:
        result = add_gem_tipped_bolts(gem)
        if result:
            print(f"Gem: {gem}")
            for key, value in result.items():
                print(f"  {key}: {value}")
            print("\n")
        else:
            print(f"Failed to add gem-tipped bolts for Gem: '{gem}'\n")

def main():
    """
    Main function to execute test cases and demonstrate functionality.
    """
    # Fetch mapping data
    mapping_data = fetch_mapping_data()

    if not mapping_data:
        logger.error("Cannot proceed without mapping data.")
        return

    # Test get_item_id
    test_get_item_id(mapping_data)

    # Test get_osrs_price
    test_get_osrs_price()

    # Test add_gem_tipped_bolts
    test_add_gem_tipped_bolts()

if __name__ == "__main__":
    main()
