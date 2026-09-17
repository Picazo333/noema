from noema.cli import main


def test_init_generates_minimal_conformant_project(tmp_path):
    code = main(["init","--root",str(tmp_path),"--id","demo","--name","Demo","--profile","minimal"])
    assert code == 0
    assert (tmp_path/"noema.project.yaml").exists()
    assert (tmp_path/"AGENTS.md").exists()
    assert main(["lint",str(tmp_path)]) == 0
