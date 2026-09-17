from noema.cli import main


def test_harvest_candidate_roundtrip(tmp_path):
    assert main(["init","--root",str(tmp_path),"--id","demo","--name","Demo","--profile","minimal"]) == 0
    assert main(["harvest","new",str(tmp_path),"--finding","Reusable context pattern","--route","noema"]) == 0
    files=list((tmp_path/"harvest").glob("*.yaml"))
    assert len(files)==1
    assert main(["harvest","validate",str(files[0])]) == 0
