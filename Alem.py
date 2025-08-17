import sys
from pathlib import Path

# Add the alem_app directory to the Python path
sys.path.append(str(Path(__file__).parent / 'alem_app'))

from alem_app.main import main

if __name__ == "__main__":
    main()