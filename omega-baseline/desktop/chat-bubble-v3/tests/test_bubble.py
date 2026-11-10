import importlib.util,pathlib,unittest,ast,sys
P=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'app'))
s=importlib.util.spec_from_file_location('bubble',P/'app/chat_bubble.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_edges(self):
  for x,y in ((0,0),(1100,500),(500,350)):
   (bx,by,w,h),_=m.placement((x,y,192,208),(1280,692))
   self.assertGreaterEqual(bx,0);self.assertGreaterEqual(by,0);self.assertLessEqual(bx+w,1280);self.assertLessEqual(by+h,692)
 def test_anchored_above(self):
  r,above=m.placement((500,400,192,208),(1280,692));self.assertTrue(above);self.assertEqual(r[1]+r[3],388)
 def test_no_legacy_click(self):
  t=ast.parse((P/'app/companion.py').read_text())
  for n in ast.walk(t):
   if isinstance(n,ast.FunctionDef) and n.name in ('release','head_activate'):
    self.assertNotIn('control.show_all',ast.unparse(n));self.assertIn('bubble.show()',ast.unparse(n))

 def test_tiny_output(self):
  for cw,ch in ((1,1),(40,20),(120,90),(3840,2160)):
   (x,y,w,h),_=m.placement((500,500,192,208),(cw,ch))
   self.assertTrue(0<=x<x+w<=cw)
   self.assertTrue(0<=y<y+h<=ch)
