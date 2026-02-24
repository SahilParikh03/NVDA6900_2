"""
Project initialization module for the backend service.

This module ensures proper directory structure and initializes necessary components.
"""

import os

def ensure_directory_structure():
    """Create necessary directories if they don't exist."""
    directories = [
        'backend/routes',
        'backend/engines'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

# Create directory structure when module is imported
ensure_directory_structure()