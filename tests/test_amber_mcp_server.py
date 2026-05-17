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


class TestValidationTools:
    def test_validate_step_missing_mdout_returns_fail(self):
        result = server.validate_step(mdout_file="/nonexistent/prod.mdout")
        assert result["status"] == "ok"
        assert result["validation"]["status"] == "FAIL"
        assert result["validation"]["checks"][0]["check"] == "file_exists"

    def test_validate_tleap_missing_log_returns_fail(self):
        result = server.validate_tleap(log_file="/nonexistent/tleap.log")
        assert result["status"] == "ok"
        assert result["validation"]["status"] == "FAIL"
        assert result["validation"]["checks"][0]["check"] == "file_exists"

    def test_check_convergence_missing_file_returns_error(self):
        result = server.check_convergence(data_file="/nonexistent/rmsd.dat")
        assert result["status"] == "error"
        assert result["tool"] == "check_convergence"


class TestAnalysisTools:
    def test_read_mdout_missing_file_returns_error(self):
        result = server.read_mdout(mdout_file="/nonexistent/prod.mdout")
        assert result["status"] == "error"
        assert result["tool"] == "read_mdout"

    def test_read_file_tail_missing_file_returns_error(self):
        result = server.read_file_tail(file_path="/nonexistent/file.txt")
        assert result["status"] == "error"
        assert result["tool"] == "read_file_tail"

    def test_list_files_existing_dir_returns_ok(self, tmp_path):
        result = server.list_files(directory=str(tmp_path))
        assert result["status"] == "ok"
        assert "files" in result

    def test_list_files_missing_dir_returns_error(self):
        result = server.list_files(directory="/nonexistent/dir")
        assert result["status"] == "error"
        assert result["tool"] == "list_files"

    def test_check_environment_returns_dict(self):
        result = server.check_environment()
        assert isinstance(result, dict)
        assert "status" in result

    def test_plot_timeseries_missing_file_returns_error(self):
        result = server.plot_timeseries(
            data_file="/nonexistent/rmsd.dat",
            output_png="/tmp/rmsd.png",
        )
        assert result["status"] == "error"
        assert result["tool"] == "plot_timeseries"

    def test_plot_bar_missing_file_returns_error(self):
        result = server.plot_bar(
            data_file="/nonexistent/rmsf.dat",
            output_png="/tmp/rmsf.png",
        )
        assert result["status"] == "error"
        assert result["tool"] == "plot_bar"


class TestRAGTools:
    def test_rag_query_empty_question_returns_error(self):
        result = server.rag_query(question="")
        assert result["status"] == "error"
        assert result["tool"] == "rag_query"

    def test_rag_toc_returns_dict(self):
        result = server.rag_toc()
        assert isinstance(result, dict)
        assert "status" in result

    def test_rag_ingest_missing_file_returns_error(self):
        result = server.rag_ingest(manual_path="/nonexistent/manual.pdf")
        assert result["status"] == "error"
        assert result["tool"] == "rag_ingest"


class TestValidateStepTemp:
    def test_averages_section_excluded_from_temp_check(self, tmp_path):
        """AVERAGES (300.01 K) and RMS FLUCT (3.25 K) must not pollute temp avg."""
        mdout = tmp_path / "prod.mdout"
        # 5 time-series lines: last 20% slice (int(7*0.8)=5) puts AVERAGES+RMS FLUCT in the late window
        mdout.write_text(
            " NSTEP =    1000   TIME(PS) =   2.000  TEMP(K) = 299.90  PRESS =  -7.1\n"
            " NSTEP =    2000   TIME(PS) =   4.000  TEMP(K) = 300.10  PRESS =   1.2\n"
            " NSTEP =    3000   TIME(PS) =   6.000  TEMP(K) = 299.80  PRESS =  -2.1\n"
            " NSTEP =    4000   TIME(PS) =   8.000  TEMP(K) = 300.20  PRESS =   0.5\n"
            " NSTEP =    5000   TIME(PS) =  10.000  TEMP(K) = 300.00  PRESS =   0.0\n"
            "\n"
            "      A V E R A G E S   O V E R       5 S T E P S\n"
            "\n"
            " NSTEP =    5000   TIME(PS) =  10.000  TEMP(K) = 300.01  PRESS =   0.0\n"
            "\n"
            "      R M S  F L U C T U A T I O N S\n"
            "\n"
            " NSTEP =       0   TIME(PS) =   0.000  TEMP(K) =   3.25  PRESS =   0.0\n"
        )
        result = server.validate_step(
            mdout_file=str(mdout),
            target_temp=300.0,
            temp_tolerance=10.0,
        )
        assert result["status"] == "ok"
        temp_check = next(
            c for c in result["validation"]["checks"] if c["check"] == "temperature"
        )
        assert temp_check["status"] == "PASS", (
            f"Expected PASS but got {temp_check['status']}: {temp_check['detail']}"
        )
        final_temp = result["validation"]["diagnostics"]["final_temp"]
        assert final_temp > 295.0, f"final_temp {final_temp} pulled down by RMS FLUCT 3.25 K value"
        assert final_temp < 305.0, f"final_temp {final_temp} looks like AVERAGES block leaked in"


class TestDirectExecTools:
    def test_run_tleap_missing_tool_called_with_args(self, tmp_path):
        """run_tleap calls md_agent.run_tleap with correct args."""
        from unittest.mock import patch
        leap_in = tmp_path / "system.in"
        leap_in.write_text("quit\n")
        with patch("md_agent.run_tleap", return_value={"success": True, "stdout": "Done", "stderr": ""}) as mock:
            result = server.run_tleap(input_file=str(leap_in), cwd=str(tmp_path))
        mock.assert_called_once_with(str(leap_in), cwd=str(tmp_path))
        assert result["status"] == "ok"
        assert result["success"] is True

    def test_run_tleap_failure_returns_error_status(self, tmp_path):
        """run_tleap propagates failure from md_agent.run_tleap."""
        from unittest.mock import patch
        leap_in = tmp_path / "system.in"
        leap_in.write_text("quit\n")
        with patch("md_agent.run_tleap", return_value={"success": False, "stdout": "", "stderr": "tleap: command not found"}):
            result = server.run_tleap(input_file=str(leap_in))
        assert result["status"] == "error"
        assert "tleap: command not found" in result["stderr"]

    def test_run_tleap_exception_returns_error(self, tmp_path):
        """run_tleap catches exceptions and returns error dict with tool key."""
        from unittest.mock import patch
        with patch("md_agent.run_tleap", side_effect=RuntimeError("no tleap")):
            result = server.run_tleap(input_file="/any/file.in")
        assert result["status"] == "error"
        assert result["tool"] == "run_tleap"
        assert "no tleap" in result["error"]

    def test_run_cpptraj_called_with_args(self, tmp_path):
        """run_cpptraj calls md_agent.run_cpptraj with correct args."""
        from unittest.mock import patch
        cpptraj_in = tmp_path / "analysis.in"
        cpptraj_in.write_text("parm sys.prmtop\nquit\n")
        with patch("md_agent.run_cpptraj", return_value={"success": True, "stdout": "Done", "stderr": ""}) as mock:
            result = server.run_cpptraj(input_file=str(cpptraj_in), cwd=str(tmp_path))
        mock.assert_called_once_with(str(cpptraj_in), cwd=str(tmp_path))
        assert result["status"] == "ok"

    def test_run_cpptraj_failure_returns_error_status(self, tmp_path):
        """run_cpptraj propagates failure from md_agent.run_cpptraj."""
        from unittest.mock import patch
        with patch("md_agent.run_cpptraj", return_value={"success": False, "stdout": "", "stderr": "cpptraj: command not found"}):
            result = server.run_cpptraj(input_file="/any/analysis.in")
        assert result["status"] == "error"

    def test_run_cpptraj_exception_returns_error(self):
        """run_cpptraj catches exceptions and returns error dict with tool key."""
        from unittest.mock import patch
        with patch("md_agent.run_cpptraj", side_effect=RuntimeError("no cpptraj")):
            result = server.run_cpptraj(input_file="/any/analysis.in")
        assert result["status"] == "error"
        assert result["tool"] == "run_cpptraj"
        assert "no cpptraj" in result["error"]
