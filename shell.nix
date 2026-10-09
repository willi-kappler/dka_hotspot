# Development toolchain. Pins the tools; uv.lock pins the Python packages.
#
#   nix-shell          # drops you into a shell with uv, ruff and sqlite
#   uv sync            # installs the locked dependencies into .venv
#   uv run src/main.py
#
{ pkgs ? import <nixpkgs> {} }:
  pkgs.mkShell {
    nativeBuildInputs = with pkgs.buildPackages; [
      python313
      uv
      ruff
      sqlite
    ];
  }
