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
        {
          from = "github.com/Atry/tablambda";
          to = "github.com/anonymous-author/tablambda";
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

      # Windows compatibility of the produced zip. Two limits of Windows'
      # built-in Compressed Folders (Explorer's zipfldr) are encoded here:
      # MAX_PATH is 260 characters, and Explorer reports the WHOLE archive as
      # empty when a single in-archive path reaches 260, while its extraction
      # stops at the first destination path that exceeds MAX_PATH; the limit is
      # set at 200 here so that extraction into a Windows folder path of up to
      # about 60 characters still fits. Windows file systems are also
      # case-insensitive, so two entries whose paths differ only by letter case
      # overwrite each other on extraction.
      assertWindowsReadableArchive = archive: ''
        unzip -Z1 ${archive} > $TMPDIR/archive-entry-paths.txt

        overlongEntryPaths=$(awk 'length($0) >= 200' $TMPDIR/archive-entry-paths.txt)
        if [ -n "$overlongEntryPaths" ]; then
          echo "FAIL: in-archive paths of 200 characters or more (Windows MAX_PATH is 260):" >&2
          echo "$overlongEntryPaths" >&2
          exit 1
        fi

        caseInsensitiveDuplicates=$(tr 'A-Z' 'a-z' < $TMPDIR/archive-entry-paths.txt | sort | uniq -d)
        if [ -n "$caseInsensitiveDuplicates" ]; then
          echo "FAIL: entry paths differing only by letter case (Windows file systems are case-insensitive):" >&2
          while IFS= read -r collidingPath; do
            grep -ixF -- "$collidingPath" $TMPDIR/archive-entry-paths.txt >&2
          done <<< "$caseInsensitiveDuplicates"
          exit 1
        fi
      '';

      # --- Supplementary material for the tablambda paper ---
      # A standalone bundle of tablambda, tablambda-examples, and their only workspace
      # dependency fixpoints, with a minimal virtual-workspace root so a reviewer can
      # resolve and run it without the rest of MIXINv2.

      tablambdaSupplementarySourceFiles = lib.fileset.toSource {
        root = ../.;
        fileset = lib.fileset.unions [
          ../packages/tablambda/src
          ../packages/tablambda/tests
          ../packages/tablambda/pyproject.toml
          ../packages/tablambda/README.md
          ../packages/tablambda-examples/src
          ../packages/tablambda-examples/tests
          ../packages/tablambda-examples/pyproject.toml
          ../packages/tablambda-examples/README.md
          ../packages/fixpoints/src
          ../packages/fixpoints/pyproject.toml
          ../packages/fixpoints/README.md
          ../packages/fixpoints/tests
          ../LICENSE
        ];
      };

      tablambdaReviewerReadme = pkgs.writeText "README.md" ''
        # tablambda -- Supplementary Material

        This archive contains `tablambda`, a tabled pure lambda-calculus interpreter
        and compiler, the example applications `tablambda-examples`, and their only
        dependency `fixpoints`.

        ## Directory structure

        - `tablambda-appendix.pdf` -- the paper's appendices, submitted here as
          supplemental material rather than in the main submission PDF.
        - `packages/tablambda/src/tablambda/` -- the tabled interpreter
          (`TabledWHNF`) and the defunctionalization compiler (`DEFUN`), together
          with a prelude of Church numerals, Scott-encoded data types, and standard
          combinators.
        - `packages/tablambda/tests/` -- the paper's examples as tests, including the
          cyclic stream `Y (cons 0)`, the unproductive cycles `Omega` and `Y (lambda x. x)`,
          the naive walk, and the ordinary `map` folding a cyclic list.
        - `packages/tablambda-examples/src/tablambda_examples/` -- example applications
          written as pure lambda terms (HOAS): edit distance, cyclic zeros, Omega, map
          over a cyclic stream, minimax game search, and an even-parity DFA;
          their committed defunctionalized (compiled) modules; and a benchmark comparing
          interpreted versus compiled execution.
        - `packages/tablambda-examples/tests/` -- tests for the example applications.
        - `packages/fixpoints/src/fixpoints/` -- least-fixpoint cached-property infrastructure.

        ## Running tests

        Requires Python >= 3.11 and [uv](https://docs.astral.sh/uv/).
        A `uv.lock` is included for reproducible dependency resolution.

        ```
        uv sync
        uv run pytest packages/tablambda/tests packages/tablambda-examples/tests packages/fixpoints/tests
        ```
      '';

      tablambdaSupplementaryMaterial = pkgs.stdenv.mkDerivation {
        name = "tablambda-supplementary-material.zip";
        src = tablambdaSupplementarySourceFiles;
        nativeBuildInputs = [ pkgs.zip pkgs.unzip ];

        buildPhase = ''
          cd ..
          mv source tablambda-supplementary-material
          cd tablambda-supplementary-material

          # The real workspace root (anonymized below) and its lockfile for
          # reproducible dependency resolution, plus a reviewer-oriented README.
          cp ${../pyproject.toml} pyproject.toml
          cp ${../uv.lock} uv.lock
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

          # Openable and extractable on Windows.
          ${assertWindowsReadableArchive "$out"}

          # No identity leaks.
          ${assertNoIdentityLeak "$base"}

          # All three packages present.
          test -d $base/packages/tablambda/src/tablambda
          test -d $base/packages/tablambda/tests
          test -d $base/packages/tablambda-examples/src/tablambda_examples
          test -d $base/packages/tablambda-examples/tests
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
