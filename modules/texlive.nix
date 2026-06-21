{ flake-parts-lib, ... }: {
  # Expose the paper's TeXLive package list as a per-system option so the monorepo
  # development environment can install the same TeX into its dev shell while this
  # subrepo only produces the appendix PDF artifact (no dev shell here).
  options.perSystem = flake-parts-lib.mkPerSystemOption ({ lib, ... }: {
    options.coLambdaTexlivePackages = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      description = "TeXLive package names for the co-lambda paper build and the dev-shell TeX.";
    };
  });
  config.perSystem = { pkgs, lib, ... }:
    let
      # TeXLive packages shared by the dev-shell paper build and the standalone appendix
      # PDF derivation below.
      texlivePackages = [
        "scheme-medium"
        "cjk"
        "xpinyin"
        "latexmk"
        # acmart dependencies not in scheme-medium
        "xstring"
        "totpages"
        "environ"
        "trimspaces"
        "ncctools"
        "comment"
        "pbalance"
        # upquote: listings renders straight quotes in the generated code
        "upquote"
        "libertine"
        "inconsolata"
        "newtx"
        "hyperxmp"
        "ifmtarg"
        "draftwatermark"
        "preprint"
        "tex-gyre"
        "multirow"
        "zref"
        # algorithm2e for the section 2 weak-head / tabling pseudocode
        "algorithm2e"
        "relsize"
        "ifoddpage"
        # pgf/tikz for the section 3 edit-distance call-tree / DP-grid figure
        "pgf"
        # breqn auto-breaks the generated edit-distance code listing (long lambda terms).
        # It bundles flexisym/mathstyle but requires expl3, so l3kernel/l3packages come with it.
        "breqn"
        "l3kernel"
        "l3packages"
      ];

      paperTexlive = pkgs.texlive.combine
        (lib.genAttrs texlivePackages (name: pkgs.texlive.${name}));

      # The appendix-only build (supplement.tex) of a paper, for inclusion
      # in its anonymized supplementary-material bundle (see
      # modules/python.nix). POPL 2027 requires appendices to be submitted
      # as separate supplemental material rather than in the main
      # submission PDF. supplement.tex sets the acmart `anonymous' option,
      # so the rendered PDF carries no author identity.
      mkPaperPdf = { name, root, fileset, entry ? "supplement" }:
        pkgs.stdenv.mkDerivation {
          inherit name;
          src = lib.fileset.toSource { inherit root fileset; };
          nativeBuildInputs = [ paperTexlive ];
          # Reproducible PDF: fix the timestamp pdftex embeds.
          SOURCE_DATE_EPOCH = "1";
          buildPhase = ''
            runHook preBuild
            export HOME=$TMPDIR
            export TEXMFVAR=$TMPDIR/texmf-var
            latexmk -pdf -interaction=nonstopmode -halt-on-error ${entry}.tex
            runHook postBuild
          '';
          installPhase = ''
            runHook preInstall
            cp ${entry}.pdf $out
            runHook postInstall
          '';
        };

      coLambdaSources = lib.fileset.unions [
        ../papers/co-lambda/co-lambda.tex
        ../papers/co-lambda/supplement.tex
        ../papers/co-lambda/supplement-xref.tex
        ../papers/co-lambda/submission.tex
        ../papers/co-lambda/preprint.tex
        ../papers/co-lambda/acmart.cls
        ../papers/co-lambda/ACM-Reference-Format.bst
        ../papers/co-lambda/references.bib
        ../papers/co-lambda/latexmkrc
        ../papers/co-lambda/generated
      ];

      coLambdaAppendixPdf = mkPaperPdf {
        name = "co-lambda-appendix.pdf";
        root = ../papers/co-lambda;
        fileset = coLambdaSources;
      };

      coLambdaSubmissionPdf = mkPaperPdf {
        name = "co-lambda-submission.pdf";
        root = ../papers/co-lambda;
        fileset = coLambdaSources;
        entry = "submission";
      };
    in {
      coLambdaTexlivePackages = texlivePackages;
      packages.co-lambda-appendix = coLambdaAppendixPdf;
      packages.co-lambda-submission = coLambdaSubmissionPdf;
    };
}
