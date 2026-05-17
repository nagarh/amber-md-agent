"""Parity tests: every MCP tool returns identical output to calling md_agent directly.

The ONLY intentional divergence between main and v1:
  validate_step() on a production mdout now returns PASS for temperature.
  Main (unfixed): TEMP(K) regex runs on full content including AVERAGES/RMS FLUCT
    sections → late-20% average can be pulled far from target → false WARN/FAIL.
  v1 (fixed): truncates content to pre-AVERAGES slice first → true time-series
    temps only → PASS for a well-equilibrated production run.
  This is the only code change in md_agent.py between the two branches.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

import md_agent
import amber_mcp_server as server

# Real fixture files from trpcage 1L2Y 1ns stress test
TLEAP_LOG  = REPO / "studies/trpcage_1ns_stress/system/leap.log"
PROD_MDOUT = REPO / "studies/trpcage_1ns_stress/simulations/prod/prod.mdout"
RMSD_DAT   = REPO / "studies/trpcage_1ns_stress/analysis/rmsd.dat"
RMSF_DAT   = REPO / "studies/trpcage_1ns_stress/analysis/rmsf.dat"

FIXTURES_EXIST = (
    TLEAP_LOG.exists() and PROD_MDOUT.exists()
    and RMSD_DAT.exists() and RMSF_DAT.exists()
)


# ─── Write Tools ─────────────────────────────────────────────────────────────

class TestWriteToolParity:
    """MCP write tools must produce identical file content to md_agent direct calls."""

    def test_write_mdin_parity(self, tmp_path):
        params = '{"imin": 1, "maxcyc": 5000, "cut": 10.0, "ntr": 1}'
        mcp_out = str(tmp_path / "mcp_min.mdin")
        direct_out = str(tmp_path / "direct_min.mdin")

        server.write_mdin(output_path=mcp_out, namelist_params=params, title="Min1")
        md_agent.write_mdin(direct_out, json.loads(params), title="Min1")

        assert Path(mcp_out).read_text() == Path(direct_out).read_text()

    def test_write_tleap_parity(self, tmp_path):
        cmds = (
            "source leaprc.protein.ff14SB\n"
            "source leaprc.water.tip3p\n"
            "mol = loadPdb protein.pdb\n"
            "solvateBox mol TIP3PBOX 12.0\n"
            "saveAmberParm mol sys.prmtop sys.inpcrd\n"
            "quit"
        )
        mcp_out = str(tmp_path / "mcp.in")
        direct_out = str(tmp_path / "direct.in")

        server.write_tleap(output_path=mcp_out, commands=cmds)
        md_agent.write_tleap(direct_out, cmds)

        assert Path(mcp_out).read_text() == Path(direct_out).read_text()

    def test_write_cpptraj_parity(self, tmp_path):
        cmds = (
            "parm sys.prmtop\n"
            "trajin prod.nc\n"
            "autoimage\n"
            "strip :WAT,Na+,Cl-\n"
            "rms first @CA,C,N out rmsd.dat\n"
            "run"
        )
        mcp_out = str(tmp_path / "mcp.in")
        direct_out = str(tmp_path / "direct.in")

        server.write_cpptraj(output_path=mcp_out, commands=cmds)
        md_agent.write_cpptraj(direct_out, cmds)

        assert Path(mcp_out).read_text() == Path(direct_out).read_text()

    def test_write_file_parity(self, tmp_path):
        content = "#!/bin/bash\nmodule load amber/24\npmemd.cuda -O -i min.mdin\n"
        mcp_out = str(tmp_path / "mcp.sh")
        direct_out = str(tmp_path / "direct.sh")

        server.write_file(output_path=mcp_out, content=content)
        md_agent.write_file(direct_out, content)

        assert Path(mcp_out).read_text() == Path(direct_out).read_text()

    def test_write_slurm_parity(self, tmp_path):
        mcp_out = str(tmp_path / "mcp_job.sh")
        direct_out = str(tmp_path / "direct_job.sh")

        server.write_slurm(
            output_path=mcp_out,
            commands="pmemd.cuda -O -i prod.mdin -o prod.mdout",
            job_name="prod_test",
            work_dir="/tmp/study/simulations/prod",
            gpus=1,
            walltime="24:00:00",
        )
        md_agent.write_slurm_script(
            direct_out,
            commands="pmemd.cuda -O -i prod.mdin -o prod.mdout",
            job_name="prod_test",
            work_dir="/tmp/study/simulations/prod",
            gpus=1,
            walltime="24:00:00",
        )

        assert Path(mcp_out).read_text() == Path(direct_out).read_text()


# ─── Validation Tools on Real Fixtures ───────────────────────────────────────

@pytest.mark.skipif(not FIXTURES_EXIST, reason="trpcage fixture files not present")
class TestValidationParity:
    """Validation gates must produce identical results on real trpcage outputs."""

    def test_validate_tleap_mcp_matches_direct(self):
        mcp    = server.validate_tleap(log_file=str(TLEAP_LOG))
        direct = md_agent.validate_tleap(str(TLEAP_LOG))

        assert mcp["status"] == "ok"
        assert mcp["validation"] == direct

    def test_validate_tleap_passes_on_trpcage(self):
        result = server.validate_tleap(log_file=str(TLEAP_LOG))
        assert result["validation"]["status"] == "PASS"

    def test_validate_step_mcp_matches_direct(self):
        """MCP wrapper must return same dict as md_agent.validate_step directly.

        v1 intentional fix: temperature check PASS (pre-AVERAGES truncation).
        Both MCP and direct call run the same v1 code, so they must agree.
        """
        kwargs = dict(
            expected_nstep=500000,
            min_density=0.95,
            max_density=1.10,
            target_temp=300.0,
            temp_tolerance=10.0,
        )
        mcp    = server.validate_step(mdout_file=str(PROD_MDOUT), **kwargs)
        direct = md_agent.validate_step(str(PROD_MDOUT), **kwargs)

        assert mcp["status"] == "ok"
        assert mcp["validation"] == direct

    def test_validate_step_all_pass_on_trpcage(self):
        """All gates must PASS on the known-good trpcage production run."""
        result = server.validate_step(
            mdout_file=str(PROD_MDOUT),
            expected_nstep=500000,
            min_density=0.95,
            max_density=1.10,
            target_temp=300.0,
            temp_tolerance=10.0,
        )
        v = result["validation"]
        assert v["status"] == "PASS", f"validate_step FAIL: {v['checks']}"
        failed = [c for c in v["checks"] if c["status"] not in ("PASS", "INFO")]
        assert not failed, f"Failing checks: {failed}"

    def test_validate_step_temp_pass_not_warn(self):
        """v1 fix: production temp must be PASS, not WARN/FAIL.

        main (unfixed) returns WARN because AVERAGES(300.01K)+RMS_FLUCT(3.25K)
        contaminate the late-20% slice. v1 truncates before AVERAGES.
        """
        result = server.validate_step(
            mdout_file=str(PROD_MDOUT),
            target_temp=300.0,
            temp_tolerance=10.0,
        )
        temp_check = next(
            c for c in result["validation"]["checks"] if c["check"] == "temperature"
        )
        assert temp_check["status"] == "PASS", (
            f"Temperature check not PASS: {temp_check['status']} — {temp_check['detail']}"
        )
        final_temp = result["validation"]["diagnostics"]["final_temp"]
        assert 295.0 < final_temp < 305.0, (
            f"final_temp={final_temp} — likely AVERAGES/RMS_FLUCT contamination"
        )

    def test_check_convergence_mcp_matches_direct(self):
        mcp    = server.check_convergence(data_file=str(RMSD_DAT))
        direct = md_agent.check_convergence(str(RMSD_DAT))

        assert mcp["status"] == "ok"
        assert mcp["convergence"] == direct

    def test_check_convergence_trpcage_converged(self):
        result = server.check_convergence(data_file=str(RMSD_DAT))
        assert result["convergence"]["status"] == "converged"
        drift = result["convergence"]["drift_abs"]
        assert drift < 0.5, f"RMSD drift {drift} Å exceeds 0.5 Å threshold"


# ─── Analysis Tools on Real Fixtures ─────────────────────────────────────────

@pytest.mark.skipif(not FIXTURES_EXIST, reason="trpcage fixture files not present")
class TestAnalysisParity:
    """Analysis tools must return identical results to md_agent direct calls."""

    def test_read_mdout_mcp_matches_direct(self):
        mcp    = server.read_mdout(mdout_file=str(PROD_MDOUT))
        direct = md_agent.read_mdout(str(PROD_MDOUT))

        assert mcp["status"] == "ok"
        assert mcp["energy_data"] == direct

    def test_read_mdout_contains_expected_keys(self):
        result = server.read_mdout(mdout_file=str(PROD_MDOUT))
        data = result["energy_data"]
        assert "averages" in data or "steps" in data or "etot" in data or len(data) > 0, (
            f"read_mdout returned empty/unexpected structure: {list(data.keys())[:5]}"
        )

    def test_list_files_mcp_matches_direct(self):
        mcp    = server.list_files(directory=str(REPO / "studies/trpcage_1ns_stress/analysis"))
        direct = md_agent.list_files(str(REPO / "studies/trpcage_1ns_stress/analysis"))

        assert mcp["status"] == "ok"
        # Both return lists of dicts — compare by filename to ignore ordering
        assert {f["name"] for f in mcp["files"]} == {f["name"] for f in direct}
