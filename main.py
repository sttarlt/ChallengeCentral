import os
from app import app  # noqa: F401
import api_routes  # noqa: F401

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
