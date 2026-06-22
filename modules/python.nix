{ inputs, flake-parts-lib, ... }: {
  # Expose the reusable uv2nix build-system overrides as a per-system option so the
  # monorepo development environment composes the same package fixes into its editable
  # virtualenv. This subrepo only produces the build artifacts (benchmark + supplementary
  # material); the editable dev env and dev shell live in the monorepo.
  options.perSystem = flake-parts-lib.mkPerSystemOption ({ lib, ... }: {
    options.tablambdaPyprojectOverrides = lib.mkOption {
      type = lib.types.raw;
      description = "Reusable uv2nix overlay (final: prev: {...}) of tablambda's build-system fixes.";
    };
  });
  config.perSystem = { config, pkgs, lib, system, ... }:
    let
      workspace =
        inputs.uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ../.; };

      # Reusable, repo-agnostic build-system fixes (exposed via the option above).
      genericPyprojectOverrides = final: prev: {
        pyflyby = prev.pyflyby.overrideAttrs (old: {
          nativeBuildInputs = old.nativeBuildInputs
            ++ final.resolveBuildSystem { meson-python = [ ]; pybind11 = [ ]; };
          propagatedBuildInputs = (old.buildInputs or [ ]) ++ [ pkgs.ninja ];
        });
        uv-dynamic-versioning = prev.uv-dynamic-versioning.overrideAttrs (old: {
          nativeBuildInputs = old.nativeBuildInputs
            ++ final.resolveBuildSystem { hatchling = [ ]; };
        });
      };

      # Repo-specific: the virtual workspace-root package has no sources to install.
      localOverrides = final: prev: {
        tablambda-workspace = prev.tablambda-workspace.overrideAttrs (_: {
          buildPhase = "mkdir -p $out";
          installPhase = "true";
          nativeBuildInputs = [ ];
        });
      };

      python = pkgs.python313;

      pythonSet = (pkgs.callPackage inputs.pyproject-nix.build.packages {
        inherit python;
      }).overrideScope (lib.composeManyExtensions [
        inputs.pyproject-build-systems.overlays.wheel
        (workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
          dependencies = workspace.deps.default;
        })
        (inputs.uv2nix_hammer_overrides.overrides pkgs)
        genericPyprojectOverrides
        localOverrides
      ]);

      # --- Per-interpreter benchmark virtualenvs ---
      # Results differ markedly across interpreters, so the benchmark fragment is generated once per
      # interpreter (paper/generated/defun-benchmark-<tag>.tex). Each venv is the workspace's default
      # dependencies installed for one interpreter; the benchmark spawns its per-cell workers with that
      # venv's interpreter (sys.executable). The benchmark is CPU-bound interpreter/compiler work (deep
      # tree walks, beta reduction), the workload PyPy's JIT accelerates; pkgs.pypy3 is PyPy 7.3.20
      # (Python 3.11), satisfying requires-python >= 3.11.
      mkBenchmarkVenv = { python, name }:
        let
          benchmarkSet = (pkgs.callPackage inputs.pyproject-nix.build.packages {
            inherit python;
          }).overrideScope (lib.composeManyExtensions [
            inputs.pyproject-build-systems.overlays.wheel
            (workspace.mkPyprojectOverlay {
              sourcePreference = "wheel";
              dependencies = workspace.deps.default;
            })
            (inputs.uv2nix_hammer_overrides.overrides pkgs)
            genericPyprojectOverrides
            localOverrides
          ]);
        in
        (benchmarkSet.mkVirtualEnv name
          (builtins.removeAttrs workspace.deps.default [ "tablambda-workspace" ])).overrideAttrs
        (old: {
          venvIgnoreCollisions = [ "*" ];
          meta = (old.meta or { }) // {
            mainProgram = "tablambda-defun-benchmark";
          };
        });

      # Every interpreter gets a venv and a regen target, but only CPython 3.11 and PyPy 3.11 can run the
      # full benchmark: the mandatory bootstrap input is committed for the py311 tag alone (3.12+ cannot
      # build it). On 3.12/3.13 the regen target therefore fails loudly rather than emitting a partial
      # fragment.
      benchmarkVenvs = {
        py311 = mkBenchmarkVenv { python = pkgs.python311; name = "tablambda-benchmark-py311"; };
        py312 = mkBenchmarkVenv { python = pkgs.python312; name = "tablambda-benchmark-py312"; };
        py313 = mkBenchmarkVenv { python = pkgs.python313; name = "tablambda-benchmark-py313"; };
        pypy = mkBenchmarkVenv { python = pkgs.pypy3; name = "tablambda-benchmark-pypy"; };
      };

      # `nix run .#regen-defun-benchmark-<tag>` measures the matrix on that interpreter and writes
      # paper/generated/defun-benchmark-<tag>.tex into the working tree. The venv is read-only in the
      # Nix store, so the output directory is passed through $TABLAMBDA_GENERATED_DIR, resolved from the
      # git checkout (the generated dir is tablambda/paper/generated in the monorepo, paper/generated in
      # the standalone subrepo).
      mkRegen = tag: venv: pkgs.writeShellApplication {
        name = "regen-defun-benchmark-${tag}";
        runtimeInputs = [ pkgs.git ];
        text = ''
          repo_root=$(git rev-parse --show-toplevel)
          if [ -d "$repo_root/tablambda/paper/generated" ]; then
            generated_dir="$repo_root/tablambda/paper/generated"
          else
            generated_dir="$repo_root/paper/generated"
          fi
          export TABLAMBDA_GENERATED_DIR="$generated_dir"
          echo "regenerating defun-benchmark-${tag}.tex in $generated_dir" >&2
          exec ${lib.getExe venv}
        '';
      };

      # --- Supplementary material for double-blind review ---

      # Identity anonymization shared by every supplementary bundle. The from/to pairs are
      # rendered into substituteInPlace arguments; the leak check fails the build if any
      # de-anonymized identity survives.
      identityReplacements = [
        { from = "yang-bo@yang-bo.com"; to = "anonymous@example.com"; }
        { from = "Yang, Bo"; to = "Anonymous, Author"; }
        { from = "Bo Yang"; to = "Anonymous Author"; }
        { from = "Figure AI Inc."; to = "Anonymous Institution"; }
        { from = "Figure AI"; to = "Anonymous Institution"; }
        {
          from = "github.com/Atry/MIXINv2";
          to = "github.com/anonymous-author/anonymous-repo";
        }
      ];

      mkReplaceArgs = replacements:
        lib.concatMapStringsSep " "
        (replacement: "--replace-warn '${replacement.from}' '${replacement.to}'")
        replacements;

      assertNoIdentityLeak = dir: ''
        for identityNeedle in "Bo Yang" "yang-bo" "Figure AI"; do
          if grep -rli "$identityNeedle" ${dir}; then
            echo "FAIL: identity leak '$identityNeedle'" >&2; exit 1
          fi
        done
        if grep -rl "Atry" ${dir}; then
          echo "FAIL: identity leak 'Atry'" >&2; exit 1
        fi
      '';

      # Positive check that anonymization ran: the author line 'Yang, Bo' becomes
      # 'Anonymous, Author', which every bundle's package metadata carries.
      assertAnonymized = dir: ''
        grep -rl "Anonymous, Author" ${dir} > /dev/null
      '';

      # --- Supplementary material for the tablambda paper ---
      # A standalone bundle of tablambda and its only workspace dependency,
      # fixpoints, with a minimal virtual-workspace root so a reviewer can resolve and run
      # it without the rest of MIXINv2.

      tablambdaSupplementarySourceFiles = lib.fileset.toSource {
        root = ../.;
        fileset = lib.fileset.unions [
          ../packages/tablambda/src
          ../packages/tablambda/tests
          ../packages/tablambda/pyproject.toml
          ../packages/tablambda/README.md
          ../packages/fixpoints/src
          ../packages/fixpoints/pyproject.toml
          ../packages/fixpoints/README.md
          ../packages/fixpoints/tests
          ../LICENSE
        ];
      };

      tablambdaReviewerReadme = pkgs.writeText "README.md" ''
        # tablambda -- Supplementary Material

        This archive contains `tablambda`, an executable first-order-shape-relation
        interpreter for the pure lambda-calculus, together with its only dependency
        `fixpoints`.

        ## Directory structure

        - `tablambda-appendix.pdf` -- the paper's appendices, submitted here as
          supplemental material rather than in the main submission PDF.
        - `packages/tablambda/src/tablambda/` -- the interpreter: the
          weak-head shape relation `Sh`, the least-fixpoint readout, and four pluggable
          position congruences.
        - `packages/tablambda/tests/` -- the paper's examples as tests, including the
          cyclic stream `Y (cons 0)`, the unproductive cycles `Omega` and `Y (lambda x. x)`,
          the naive walk, and the ordinary `map` folding a cyclic list.
        - `packages/fixpoints/src/fixpoints/` -- least-fixpoint cached-property infrastructure.

        ## Running tests

        Requires Python >= 3.11 and [uv](https://docs.astral.sh/uv/).

        ```
        uv sync
        uv run pytest packages/tablambda/tests packages/fixpoints/tests
        ```
      '';

      tablambdaWorkspacePyproject = pkgs.writeText "pyproject.toml" ''
        [tool.uv.workspace]
        members = ["packages/tablambda", "packages/fixpoints"]
      '';

      tablambdaSupplementaryMaterial = pkgs.stdenv.mkDerivation {
        name = "tablambda-supplementary-material.zip";
        src = tablambdaSupplementarySourceFiles;
        nativeBuildInputs = [ pkgs.zip pkgs.unzip ];

        buildPhase = ''
          cd ..
          mv source tablambda-supplementary-material
          cd tablambda-supplementary-material

          # A minimal virtual-workspace root over just the two packages, and a
          # reviewer-oriented README. No uv.lock: the reviewer locks the two-package
          # workspace fresh, avoiding references to the absent MIXINv2 members.
          cp ${tablambdaWorkspacePyproject} pyproject.toml
          cp ${tablambdaReviewerReadme} README.md

          # The paper's appendices as a separate PDF (POPL 2027 requires
          # appendices as supplemental material). Built from supplement.tex
          # with the acmart `anonymous' option, so it carries no identity.
          cp ${config.packages.tablambda-appendix} tablambda-appendix.pdf

          # Anonymize identity in the package metadata (authors, repository URL).
          shopt -s globstar nullglob
          substituteInPlace \
            **/*.py **/*.toml **/*.md **/*.rst **/*.txt **/*.cfg \
            ${mkReplaceArgs identityReplacements}
          shopt -u globstar nullglob

          cd ..
          zip -r --latest-time \
            $TMPDIR/tablambda-supplementary-material.zip \
            tablambda-supplementary-material
        '';

        installPhase = ''
          cp $TMPDIR/tablambda-supplementary-material.zip $out
        '';

        doInstallCheck = true;
        installCheckPhase = ''
          unzip $out -d $TMPDIR/verify
          base=$TMPDIR/verify/tablambda-supplementary-material

          # No identity leaks.
          ${assertNoIdentityLeak "$base"}

          # Both packages present.
          test -d $base/packages/tablambda/src/tablambda
          test -d $base/packages/tablambda/tests
          test -d $base/packages/fixpoints/src/fixpoints

          # The appendix PDF is bundled.
          test -f $base/tablambda-appendix.pdf

          # Anonymization applied.
          ${assertAnonymized "$base"}
        '';
      };
    in {
      tablambdaPyprojectOverrides = genericPyprojectOverrides;
      packages.tablambda-benchmark-pypy = benchmarkVenvs.pypy;
      packages.regen-defun-benchmark-py311 = mkRegen "py311" benchmarkVenvs.py311;
      packages.regen-defun-benchmark-py312 = mkRegen "py312" benchmarkVenvs.py312;
      packages.regen-defun-benchmark-py313 = mkRegen "py313" benchmarkVenvs.py313;
      packages.regen-defun-benchmark-pypy = mkRegen "pypy" benchmarkVenvs.pypy;
      packages.tablambda-supplementary-material = tablambdaSupplementaryMaterial;
    };
}
