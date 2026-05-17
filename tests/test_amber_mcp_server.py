"""Smoke tests for amber_mcp_server — call functions directly, not via MCP protocol."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import amber_mcp_server as server


class TestConnectivity:
    def test_ping_returns_ok(self):
        result = server.ping()
        assert result["status"] == "ok"
        assert isinstance(result.get("message"), str)
        assert result["message"]


class TestPDBTools:
    def test_fetch_pdb_empty_id_returns_error(self):
        result = server.fetch_pdb(pdb_id="", output_dir="/tmp")
        assert result["status"] == "error"
        assert result["tool"] == "fetch_pdb"

    def test_inspect_pdb_missing_file_returns_error(self):
        result = server.inspect_pdb(pdb_file="/nonexistent/file.pdb")
        assert result["status"] == "error"
        assert result["tool"] == "inspect_pdb"

    def test_clean_pdb_missing_file_returns_error(self):
        result = server.clean_pdb(pdb_file="/nonexistent/file.pdb")
        assert result["status"] == "error"
        assert result["tool"] == "clean_pdb"

    def test_preflight_missing_file_returns_error(self):
        result = server.preflight(pdb_file="/nonexistent/file.pdb")
        assert result["status"] == "error"
        assert result["tool"] == "preflight"


class TestFileWriters:
    def test_write_tleap_creates_file(self, tmp_path):
        out = str(tmp_path / "test.in")
        result = server.write_tleap(
            output_path=out,
            commands="source leaprc.protein.ff19SB\nquit",
        )
        assert result["status"] == "ok"
        assert Path(out).exists()

    def test_write_mdin_creates_file(self, tmp_path):
        out = str(tmp_path / "min.mdin")
        result = server.write_mdin(
            output_path=out,
            namelist_params='{"imin": 1, "maxcyc": 1000, "cut": 8.0}',
            title="Test minimization",
        )
        assert result["status"] == "ok"
        assert Path(out).exists()

    def test_write_cpptraj_creates_file(self, tmp_path):
        out = str(tmp_path / "rmsd.in")
        result = server.write_cpptraj(
            output_path=out,
            commands="parm sys.prmtop\ntrajin prod.nc\nrmsd :1-100 out rmsd.dat\nrun",
        )
        assert result["status"] == "ok"
        assert Path(out).exists()

    def test_write_file_creates_file(self, tmp_path):
        out = str(tmp_path / "custom.sh")
        result = server.write_file(
            output_path=out,
            content="#!/bin/bash\necho hello",
        )
        assert result["status"] == "ok"
        assert Path(out).exists()

    def test_write_slurm_creates_file(self, tmp_path):
        out = str(tmp_path / "job.sh")
        result = server.write_slurm(
            output_path=out,
            commands="echo test",
            job_name="test_job",
        )
        assert result["status"] == "ok"
        assert Path(out).exists()


class TestSLURMTools:
    def test_submit_slurm_missing_script_returns_error(self):
        result = server.submit_slurm(script_path="/nonexistent/job.sh")
        assert result["status"] == "error"
        assert result["tool"] == "submit_slurm"

    def test_check_slurm_job_no_id_returns_dict(self):
        result = server.check_slurm_job()
        assert isinstance(result, dict)
        assert "status" in result

    def test_cancel_slurm_job_bad_id_returns_error(self):
        result = server.cancel_slurm_job(job_id="99999999")
        assert isinstance(result, dict)
        assert "status" in result

    def test_slurm_history_returns_dict(self):
        result = server.slurm_history(days=1)
        assert isinstance(result, dict)
        assert "status" in result
