"""Synthetic fixtures test the oracle, never stand in for actual GUI evidence."""
import unittest
from PIL import Image
from capture_oracle import frames, find_matches, sequence, match_at, verify_asset, rectangle, look_rectangle

class OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates=frames('running-right')
        with Image.open(verify_asset()) as im:cls.atlas=im.copy()

    def fixture(self, index=0, point=(70,80), look=None):
        im=Image.new('RGB',(420,420),(241,240,239))
        x,y,w,h=rectangle('running-right',index) if look is None else look_rectangle(look)
        cell=self.atlas.crop((x,y,x+w,y+h))
        im.paste(cell,point,cell)
        return im

    def test_exact_match_and_origin(self):
        found=find_matches(self.fixture(),self.candidates)
        self.assertTrue(any((m['frame'],m['x'],m['y'])==(0,70,80) for m in found))
        self.assertTrue(all(m['mismatched_opaque_pixels']==0 and m['opaque_pixels']>1000 for m in found))

    def test_one_opaque_pixel_corruption_fails(self):
        im=self.fixture();x,y,rgb=self.candidates[0]['opaque'][50]
        im.putpixel((70+x,80+y),tuple(v^255 for v in rgb))
        self.assertFalse(match_at(im,self.candidates[0],70,80)['passed'])
        self.assertEqual(find_matches(im,self.candidates,(70,80)),[])

    def test_background_ignored_for_source_match(self):
        im=self.fixture();im.putpixel((70,80),(123,45,67))
        self.assertTrue(find_matches(im,self.candidates,(70,80)))

    def test_animation_and_pause(self):
        ims=[self.fixture(i) for i in range(3)]
        self.assertTrue(sequence(ims,self.candidates,[0,160,320],'animation')['passed'])
        self.assertFalse(sequence(ims,self.candidates,[0,160,320],'pause')['passed'])
        still=[self.fixture() for _ in range(3)]
        self.assertTrue(sequence(still,self.candidates,[0,160,320],'pause')['passed'])
        self.assertFalse(sequence(still,self.candidates,[0,160,320],'animation')['passed'])

    def test_pause_detects_cursor_or_background_change(self):
        ims=[self.fixture() for _ in range(3)];ims[1].putpixel((70,80),(0,0,0))
        self.assertFalse(sequence(ims,self.candidates,[0,160,320],'pause')['passed'])
        self.assertFalse(sequence(ims,self.candidates,[0,160,320],'animation')['passed'])

    def test_moved_sprite_and_blank_fail(self):
        self.assertFalse(sequence([self.fixture(),self.fixture(point=(71,80)),self.fixture()],self.candidates,[0,160,320],'pause')['passed'])
        self.assertEqual(find_matches(Image.new('RGB',(420,420)),self.candidates),[])

    def test_reject_insufficient_timing_or_count(self):
        for times in ([0,1,2],[200,100,300],[0,125]):
            with self.assertRaises(ValueError):sequence([self.fixture() for _ in range(3)],self.candidates,times,'pause')
        with self.assertRaises(ValueError):sequence([self.fixture()],self.candidates,[0],'pause')

    def test_look_directions(self):
        for direction in (0,8):
            self.assertTrue(find_matches(self.fixture(look=direction),frames(look=direction),(70,80)))
            self.assertFalse(find_matches(self.fixture(look=direction),frames(look=8-direction),(70,80)))

    def test_duplicate_windows_rejected(self):
        im=Image.new('RGB',(800,420),(241,240,239));im.paste(self.fixture(),(0,0));im.paste(self.fixture(),(380,0))
        result=sequence([im]*3,self.candidates,[0,160,320],'pause')
        self.assertFalse(result['passed'])

    def test_out_of_bounds(self):
        self.assertFalse(match_at(self.fixture(),self.candidates[0],-1,80)['passed'])

if __name__=='__main__':unittest.main()
