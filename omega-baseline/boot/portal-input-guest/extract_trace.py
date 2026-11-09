"""Preserve selected original protocol lines; never synthesize input/frame evidence."""
import argparse,json,re
from pathlib import Path
PATTERN=re.compile(r'(?:wl_keyboard|wl_pointer|wl_surface|wl_callback|xdg_surface|xdg_toplevel|wl_shm_pool|wl_buffer)[@#]\d+\.(?:enter|leave|key|modifiers|motion|button|frame|configure|ack_configure|attach|commit|done|release|create_buffer)\(')
def extract(text):
 return [{'serial_line':n,'raw_line':line} for n,line in enumerate(text.splitlines(),1) if PATTERN.search(line)]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('serial');p.add_argument('output');a=p.parse_args();out=Path(a.output)
 with out.open('x') as f:json.dump({'clock_warning':'Raw Wayland timestamps and host QMP elapsed values are different clocks; correlate by event sequence, not invented wall-clock equivalence.','events':extract(Path(a.serial).read_text(errors='replace'))},f,indent=2)
