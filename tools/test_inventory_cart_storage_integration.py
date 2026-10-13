"""Run the current three UI payloads in memory after deselecting the legacy skin.

The reference client is read only. Only the known ROGlobalZeroInventory records
are restored from pristine source in emulator memory, exactly as WARP removes
that patch's staged writes. No client image is serialized or executed as a process.
"""
import argparse
from pathlib import Path
import sys
import pefile
from test_modern_chat_ui import Machine
import test_inventory_cart_payloads as inventory_cart
import test_storage_payload as storage

LEGACY_SITES=[(0x103D4B0,4),(0x103D4D0,4),(0x102DD94,4),
              (0x102DDB4,4),(0x93F28A,6),(0x955A33,6),(0x947477,5)]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('client',type=Path)
    ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args();pristine=pefile.PE(str(args.source))
    original_init=Machine.__init__
    def without_legacy(self,*a,**kw):
        original_init(self,*a,**kw)
        for address,length in LEGACY_SITES:
            self.u.mem_write(address,pristine.get_data(address-pristine.OPTIONAL_HEADER.ImageBase,length))
    Machine.__init__=without_legacy
    sys.argv=[sys.argv[0],str(args.client),'--output',str(args.output/'inventory-cart')]
    inventory_cart.main()
    sys.argv=[sys.argv[0],str(args.client),'--output',str(args.output/'storage')]
    storage.main()
    print('PASS three current UI payloads after legacy deselection; all client files read only')

if __name__=='__main__':main()
