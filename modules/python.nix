{ inputs, flake-parts-lib, ... }: {
  # Expose the reusable uv2nix build-system overrides as a per-system option so the
  # monorepo development environment composes the same package fixes into its editable
  # virtualenv. This subrepo only produces the build artifacts (benchmark + supplementary
  # material); the editable dev env and dev shell live in the monorepo.
  options.perSystem = flake-parts-lib.mkPerSystemOption ({ lib, ... }: {
    options.coLambdaPyprojectOverrides = lib.mkOption {
      type = lib.types.raw;
      description = "Reusable uv2nix overlay (final: prev: {...}) of co-lambda's build-system fixes.";
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
        co-lambda-workspace = prev.co-lambda-workspace.overrideAttrs (_: {
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

      # --- PyPy runtime for co-lambda-benchmark ---
      # The benchmark is CPU-bound interpreter/compiler work (deep tree walks, beta reduction),
      # the workload PyPy's JIT accelerates. pkgs.pypy3 is PyPy 7.3.20 (Python 3.11),
      # satisfying requires-python >= 3.11.
      pythonPypy = pkgs.pypy3;

      pythonSetPypy = (pkgs.callPackage inputs.pyproject-nix.build.packages {
        python = pythonPypy;
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

      coLambdaBenchmarkPypy =
        (pythonSetPypy.mkVirtualEnv "co-lambda-benchmark-pypy"
          (builtins.removeAttrs workspace.deps.default [ "co-lambda-workspace" ])).overrideAttrs
        (old: {
          venvIgnoreCollisions = [ "*" ];
          meta = (old.meta or { }) // {
            mainProgram = "co-lambda-benchmark";
          };
        });

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

      # --- Supplementary material for the co-lambda paper ---
      # A standalone bundle of co_lambda and its only workspace dependency,
      # fixpoints, with a minimal virtual-workspace root so a reviewer can resolve and run
      # it without the rest of MIXINv2.

      coLambdaSupplementarySourceFiles = lib.fileset.toSource {
        root = ../.;
        fileset = lib.fileset.unions [
          ../packages/co-lambda/src
          ../packages/co-lambda/tests
          ../packages/co-lambda/pyproject.toml
          ../packages/co-lambda/README.md
          ../packages/fixpoints/src
          ../packages/fixpoints/pyproject.toml
          ../packages/fixpoints/README.md
          ../packages/fixpoints/tests
          ../LICENSE
        ];
      };

      coLambdaReviewerReadme = pkgs.writeText "README.md" ''
        # co-lambda -- Supplementary Material

        This archive contains `co_lambda`, an executable first-order-shape-relation
        interpreter for the pure lambda-calculus, together with its only dependency
        `fixpoints`.

        ## Directory structure

        - `co-lambda-appendix.pdf` -- the paper's appendices, submitted here as
          supplemental material rather than in the main submission PDF.
        - `packages/co-lambda/src/co_lambda/` -- the interpreter: the
          weak-head shape relation `Sh`, the least-fixpoint readout, and four pluggable
          position congruences.
        - `packages/co-lambda/tests/` -- the paper's examples as tests, including the
          cyclic stream `Y (cons 0)`, the unproductive cycles `Omega` and `Y (lambda x. x)`,
          the naive walk, and the ordinary `map` folding a cyclic list.
        - `packages/fixpoints/src/fixpoints/` -- least-fixpoint cached-property infrastructure.

        ## Running tests

        Requires Python >= 3.11 and [uv](https://docs.astral.sh/uv/).

        ```
        uv sync
        uv run pytest packages/co-lambda/tests packages/fixpoints/tests
        ```
      '';

      coLambdaWorkspacePyproject = pkgs.writeText "pyproject.toml" ''
        [tool.uv.workspace]
        members = ["packages/co-lambda", "packages/fixpoints"]
      '';

      coLambdaSupplementaryMaterial = pkgs.stdenv.mkDerivation {
        name = "co-lambda-supplementary-material.zip";
        src = coLambdaSupplementarySourceFiles;
        nativeBuildInputs = [ pkgs.zip pkgs.unzip ];

        buildPhase = ''
          cd ..
          mv source co-lambda-supplementary-material
          cd co-lambda-supplementary-material

          # A minimal virtual-workspace root over just the two packages, and a
          # reviewer-oriented README. No uv.lock: the reviewer locks the two-package
          # workspace fresh, avoiding references to the absent MIXINv2 members.
          cp ${coLambdaWorkspacePyproject} pyproject.toml
          cp ${coLambdaReviewerReadme} README.md

          # The paper's appendices as a separate PDF (POPL 2027 requires
          # appendices as supplemental material). Built from supplement.tex
          # with the acmart `anonymous' option, so it carries no identity.
          cp ${config.packages.co-lambda-appendix} co-lambda-appendix.pdf

          # Anonymize identity in the package metadata (authors, repository URL).
          shopt -s globstar nullglob
          substituteInPlace \
            **/*.py **/*.toml **/*.md **/*.rst **/*.txt **/*.cfg \
            ${mkReplaceArgs identityReplacements}
          shopt -u globstar nullglob

          cd ..
          zip -r --latest-time \
            $TMPDIR/co-lambda-supplementary-material.zip \
            co-lambda-supplementary-material
        '';

        installPhase = ''
          cp $TMPDIR/co-lambda-supplementary-material.zip $out
        '';

        doInstallCheck = true;
        installCheckPhase = ''
          unzip $out -d $TMPDIR/verify
          base=$TMPDIR/verify/co-lambda-supplementary-material

          # No identity leaks.
          ${assertNoIdentityLeak "$base"}

          # Both packages present.
          test -d $base/packages/co-lambda/src/co_lambda
          test -d $base/packages/co-lambda/tests
          test -d $base/packages/fixpoints/src/fixpoints

          # The appendix PDF is bundled.
          test -f $base/co-lambda-appendix.pdf

          # Anonymization applied.
          ${assertAnonymized "$base"}
        '';
      };
    in {
      coLambdaPyprojectOverrides = genericPyprojectOverrides;
      packages.co-lambda-benchmark-pypy = coLambdaBenchmarkPypy;
      packages.co-lambda-supplementary-material = coLambdaSupplementaryMaterial;
    };
}
