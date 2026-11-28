"""Small adversarial saved-byte fixtures; no benchmark, Git or network."""
import base64
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('compact_saved_replay',Path(__file__).with_name('replay.py'))
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
NAME=R.PREFIX+'fixture.txt'
RAW=b'original LF bytes\nNn\x00\xff'


def identity(raw=RAW,name=NAME,mode='100644'):
    return dict(path=name,mode=mode,bytes=len(raw),sha256=R.digest(raw),git_oid=R.git_oid('blob',raw))


def archive(path,items):
    with tarfile.open(path,'w:gz',format=tarfile.USTAR_FORMAT) as tar:
        for name,raw,kind,link in items:
            member=tarfile.TarInfo(name);member.mode=0o644;member.type=kind;member.linkname=link
            member.size=len(raw) if kind==tarfile.REGTYPE else 0
            tar.addfile(member,io.BytesIO(raw) if member.size else None)


class Extraction(unittest.TestCase):
    def test_exact_bytes_mode_and_git_blob(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);bundle=root/'e.tar.gz';out=root/'out';out.mkdir()
            archive(bundle,[(NAME,RAW,tarfile.REGTYPE,'')])
            self.assertEqual(R.safe_extract(bundle,[identity()],out),len(RAW))
            self.assertEqual((out/NAME).read_bytes(),RAW)

    def test_unsafe_names_rejected_before_any_escape(self):
        names=('../outside','/absolute','evidence/../outside','evidence\\outside','C:/outside',
               'evidence//outside','evidence/tb-lvl-0/CON','evidence/tb-lvl-0/name.')
        for name in names:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as td:
                root=Path(td);out=root/'out';out.mkdir();bundle=root/'e.tar.gz'
                archive(bundle,[(name,RAW,tarfile.REGTYPE,'')])
                with self.assertRaises(ValueError):R.safe_extract(bundle,[identity()],out)
                self.assertEqual(list(out.rglob('*')),[])

    def test_links_and_duplicate_members_rejected(self):
        variants=[[(NAME,b'',tarfile.SYMTYPE,'../../outside')],[(NAME,b'',tarfile.LNKTYPE,NAME)],
                  [(NAME,RAW,tarfile.REGTYPE,''),(NAME,RAW,tarfile.REGTYPE,'')]]
        for items in variants:
            with self.subTest(items=items),tempfile.TemporaryDirectory() as td:
                root=Path(td);out=root/'out';out.mkdir();bundle=root/'e.tar.gz';archive(bundle,items)
                with self.assertRaises(ValueError):R.safe_extract(bundle,[identity()],out)

    def test_pax_path_override_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);bundle=root/'e.tar.gz';out=root/'out';out.mkdir()
            with tarfile.open(bundle,'w:gz',format=tarfile.PAX_FORMAT) as tar:
                item=tarfile.TarInfo(NAME);item.size=len(RAW);item.mode=0o644;item.pax_headers={'path':'../outside'}
                tar.addfile(item,io.BytesIO(RAW))
            with self.assertRaises(ValueError):R.safe_extract(bundle,[identity()],out)

    def test_changed_member_hash_length_mode_and_missing(self):
        variants=[([(NAME,RAW+b'x',tarfile.REGTYPE,'')],identity()),
                  ([(NAME,RAW.replace(b'Nn',b'NN'),tarfile.REGTYPE,'')],identity()),
                  ([(NAME,RAW,tarfile.REGTYPE,'')],dict(identity(),sha256='0'*64)),
                  ([(NAME,RAW,tarfile.REGTYPE,'')],dict(identity(),git_oid='0'*40)),
                  ([(NAME,RAW,tarfile.REGTYPE,'')],identity(mode='100755')),
                  ([],identity())]
        for items,row in variants:
            with self.subTest(row=row,items=items),tempfile.TemporaryDirectory() as td:
                root=Path(td);out=root/'out';out.mkdir();bundle=root/'e.tar.gz';archive(bundle,items)
                with self.assertRaises(ValueError):R.safe_extract(bundle,[row],out)

    def test_case_alias_and_noncanonical_inventory(self):
        with self.assertRaises(ValueError):R.file_map([identity(),identity(name=NAME.upper())])
        with self.assertRaises(ValueError):R.file_map([identity(name='other/source.py')])
        with self.assertRaises(ValueError):R.file_map([identity(),identity()])


class SourceAndMirrors(unittest.TestCase):
    def mirror_fixture(self,outer,saved):
        mirrors=[dict(path=path,source_path=source) for path,source in R.MIRRORS.items()]
        for item in mirrors:
            for base,name in ((outer,item['path']),(saved,item['source_path'])):
                (base/name).parent.mkdir(parents=True,exist_ok=True);(base/name).write_bytes(b'accepted\n')
        return mirrors

    def test_altered_accepted_outer_view_is_not_newline_normalized(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);outer=root/'outer';saved=root/'saved';name=R.PREFIX+'RESULTS.md'
            mirrors=self.mirror_fixture(outer,saved)
            self.assertEqual(R.verify_mirrors(outer,saved,mirrors),sorted(R.MIRRORS))
            (outer/name).write_bytes(b'accepted\r\n')
            with self.assertRaises(ValueError):R.verify_mirrors(outer,saved,mirrors)

    def test_calibration_mirror_cannot_be_removed_or_substituted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);outer=root/'outer';saved=root/'saved';cal=R.PREFIX+'CALIBRATION.md'
            mirrors=self.mirror_fixture(outer,saved);self.assertEqual(len(mirrors),14)
            (outer/cal).write_bytes(b'changed calibration\n')
            without=[m for m in mirrors if m['path']!=cal]
            substituted=[dict(m,source_path=R.PREFIX+'PROTOCOL.md') if m['path']==cal else m for m in mirrors]
            duplicated=without+[dict(without[0])]
            for altered in (mirrors,without,substituted,duplicated):
                with self.subTest(mirrors=altered),self.assertRaises(ValueError):
                    R.verify_mirrors(outer,saved,altered)

    def test_adapter_sources_schema_mappings_and_upstream_are_bound(self):
        original=dict(schema='tb-lvl-0-adapter-sources-v1',source_commit=R.SOURCE,
            mirrors=[dict(path=p,source_path=s) for p,s in R.ADAPTER_MIRRORS.items()],upstream=[R.EXTRA])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);name=R.PREFIX+'adapters/SOURCES.json';path=root/name;path.parent.mkdir(parents=True)
            raw=R.packed(original);path.write_bytes(raw)
            self.assertEqual(R.verify_adapter_sources(root),dict(path=name,bytes=len(raw),sha256=R.digest(raw)))
            variants=[]
            for field,value in (('schema','other'),('source_commit','0'*40),('mirrors',original['mirrors'][:1]),
                                ('mirrors',[dict(original['mirrors'][0],source_path=R.PREFIX+'audit.py'),original['mirrors'][1]]),
                                ('upstream',[dict(R.EXTRA,commit='0'*40)]),('upstream',[])):
                variants.append(dict(original,**{field:value}))
            variants.append(dict(original,unbound_field='tampered'))
            for changed in variants:
                path.write_bytes(R.packed(changed))
                with self.subTest(value=changed),self.assertRaises(ValueError):R.verify_adapter_sources(root)

    def test_git_tree_entry_and_duplicate_validation(self):
        entry=b'100644 file\0'+bytes.fromhex('1'*40)
        self.assertEqual(R.parse_tree(entry),{'file':('100644','1'*40)})
        with self.assertRaises(ValueError):R.parse_tree(entry+entry)
        with self.assertRaises(ValueError):R.parse_tree(b'100644 ../escape\0'+bytes(20))

    def test_source_commit_cannot_be_replaced(self):
        fake=b'tree '+b'1'*40+b'\n\nsynthetic\n'
        bundle=dict(source_commit=R.SOURCE,git=dict(commit_base64=base64.b64encode(fake).decode(),trees=[]))
        with self.assertRaisesRegex(ValueError,'commit object'):R.verify_git(bundle,{})

    def test_fixed_output_anchors_and_no_native_cli(self):
        self.assertEqual(set(R.ACCEPTED),{'audit.json','analysis.json','RESULTS.md'})
        with self.assertRaises(ValueError):R.check_accepted({name:b'changed' for name in R.ACCEPTED})
        self.assertEqual(R.SOURCE,'25f9459c87485a1d47950ebea031e39ec441942a')


if __name__=='__main__':unittest.main()
