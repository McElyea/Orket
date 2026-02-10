from typing import Union, Type


def normalize_price(price_input: Union[str, int, float]) -> float:
    """
    Normalizes a price input into a float.
    
    Args:
        price_input: A string, integer, or float representing the price.
        
    Returns:
        float: The normalized price.
        
    Raises:
        ValueError: If the input is None, empty, or cannot be converted to a valid float.
        TypeError: If the input is not a string, int, or float.
    """
    if price_input is None:
        raise ValueError("Price input cannot be None")

    if isinstance(price_input, (int, float)):
        return float(price_input)
        
    if not isinstance(price_input, str):
        raise TypeError(f"Expected str, int, or float, got {type(price_input).__name__}")
        
    clean_str = price_input.replace(',', '').strip()
    if not clean_str:
        raise ValueError("Price string is empty")
        
    try:
        return float(clean_str)
    except ValueError:
        raise ValueError(f"Could not normalize invalid price string: '{price_input}'")
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
