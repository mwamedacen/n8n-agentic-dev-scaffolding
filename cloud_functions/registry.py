"""
Function Registry

Imports and exposes cloud functions for dynamic endpoint registration.
"""

from functions.hello_world import hello_world
from functions.validate_purchase_orders import validate_purchase_orders

EXPOSED_FUNCTIONS = {
    "hello_world": hello_world,
    "validate_purchase_orders": validate_purchase_orders,
}
