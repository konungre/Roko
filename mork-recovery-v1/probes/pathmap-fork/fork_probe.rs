use pathmap::PathMap;
use pathmap::zipper::{ZipperForking, ZipperMoving, ZipperPath};
use pathmap::zipper::PrefixZipper;
fn main() {
    let mut map = PathMap::<u64>::new();
    map.set_val_at(b"ab", 1);
    map.set_val_at(b"abc", 2);
    let mut parent = PrefixZipper::new(&b"xy"[..], map.read_zipper());
    parent.descend_to(b"xya");
    let mut child = parent.fork_read_zipper();
    let mut paths = Vec::new();
    while child.to_next_step() {
        paths.push(child.path().to_vec());
        assert!(paths.len() < 16, "bounded probe traversal exceeded");
    }
    println!("fork_at=xya expected={:?} actual={:?}", vec![b"b".to_vec(), b"bc".to_vec()], paths);
    assert_eq!(paths, vec![b"b".to_vec(), b"bc".to_vec()], "fork must start at current focus");
}
