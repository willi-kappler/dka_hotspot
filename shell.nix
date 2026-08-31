# Development toolchain. Pins the tools; uv.lock pins the Python packages.
#
#   nix-shell          # drops you into a shell with uv, ruff and sqlite
#   uv sync            # installs the locked dependencies into .venv
#   uv run src/main.py
#
# On NixOS set "programs.nix-ld.enable = true;" in configuration.nix. uv
# installs manylinux wheels (numpy, scipy, pandas, statsmodels ship compiled
# binaries) and those need a conventional dynamic loader to run.
{ pkgs ? import <nixpkgs> {} }:
  pkgs.mkShell {
    nativeBuildInputs = with pkgs.buildPackages; [
      # 3.13 is what development runs on; CI additionally covers the 3.11
      # floor declared in pyproject.toml.
      python313
      uv
      ruff
      # For the health checks in OPERATIONS.md (integrity_check, audit counts).
      sqlite
    ];
  }
