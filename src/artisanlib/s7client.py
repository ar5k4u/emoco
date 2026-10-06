#

import snap7.client
try:
    from typing import override
except ImportError:
    from typing_extensions import override

# patch S7 client


class S7Client(snap7.client.Client):
    def __init__(self) -> None:
        super().__init__()

    # avoiding an exception on __del__ as self.library might not yet be set if loading of shared lib failed!
    @override
    def destroy(self) -> None:
        if hasattr(self, 'library'):
            super().destroy()
