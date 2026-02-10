from typing import Any, Optional

def normalize_price(price_str: Any) -> float:
    """
    Normalizes a price string into a float.
    
    Preconditions:
        - price_str should be a string or something convertible to string.
        - Should contain numeric values, potentially with commas.
        
    Returns:
        float: The normalized price.
        
    Raises:
        ValueError: If the price_str cannot be normalized to a valid float.
    """
    if price_str is None:
        raise ValueError("Price string cannot be None")
        
    if not isinstance(price_str, str):
        price_str = str(price_str)
        
    clean_str = price_str.replace(',', '').strip()
    if not clean_str:
        raise ValueError("Price string is empty")
        
    try:
        return float(clean_str)
    except ValueError:
        raise ValueError(f"Could not normalize invalid price string: '{price_str}'")
