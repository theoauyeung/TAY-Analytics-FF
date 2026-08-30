"""Launch the TAY Analytics FF API server."""
from __future__ import annotations
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import uvicorn

if __name__ == '__main__':
    uvicorn.run(
        'tay.api.app:app',
        host='0.0.0.0',
        port=8000,
        reload=True,
        reload_dirs=['src'],
    )
