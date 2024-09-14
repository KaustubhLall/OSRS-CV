from pathlib import Path

ASSETS_ROOT = Path(__file__).parent / "../assets"


def load_assets(path=ASSETS_ROOT):
    assets = {}

    # Check if the path exists and is a directory
    if not path.exists():
        raise FileNotFoundError(f"The specified assets root path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"The specified path is not a directory: {path}")

    # Automatically discover categories by finding directories
    try:
        for category_path in path.iterdir():
            if category_path.is_dir():
                category_name = category_path.name
                assets[category_name] = {}

                # List all files in each category directory
                for file in category_path.glob('*.*'):  # Including all files
                    if file.is_file():
                        # Use the stem of the file as the key, and the relative path as the value
                        assets[category_name][file.stem] = str(file.absolute())
    except PermissionError as e:
        raise PermissionError(f"Permission denied when accessing directory: {e}")
    except Exception as e:
        raise Exception(f"An error occurred while loading assets: {e}")

    return assets


# Example usage:
if __name__ == '__main__':
    try:
        asset_dict = load_assets()
        print(asset_dict)
    except Exception as e:
        print(f"Failed to load assets: {e}")
