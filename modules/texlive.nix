{ flake-parts-lib, ... }: {
  # Expose the paper's TeXLive package list as a per-system option so the monorepo
  # development environment can install the same TeX into its dev shell while this
  # subrepo only produces the appendix PDF artifact (no dev shell here).
  options.perSystem = flake-parts-lib.mkPerSystemOption ({ lib, ... }: {
    options.tablambdaTexlivePackages = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      description = "TeXLive package names for the tablambda paper build and the dev-shell TeX.";
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
        # CJKutf8 (from cjk) renders the Chinese preprint (preprint-zh.tex) under
        # pdfLaTeX, like the English entries; arphic supplies the gbsn (SongTi)
        # Type1 font it uses, so the build needs no system fonts.
        "arphic"
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
        # autobreak wraps the long lambda terms in the appendix code listings,
        # breaking them at source line ends inside align*.
        "autobreak"
        # expl3 runtime, used by acmart and other packages.
        "l3kernel"
        "l3packages"
        # Springer's llncs class and splncs04 bibliography style, for the LNCS
        # entry (flops.tex).
        "llncs"
      ];

      paperTexlive = pkgs.texlive.combine
        (lib.genAttrs texlivePackages (name: pkgs.texlive.${name}));

      # The appendix-only build (supplement.tex) of a paper, for inclusion
      # in its anonymized supplementary-material bundle (see
      # modules/python.nix). POPL 2027 requires appendices to be submitted
      # as separate supplemental material rather than in the main
      # submission PDF. supplement.tex sets the acmart `anonymous' option,
      # so the rendered PDF carries no author identity.
      # Scan a rendered anonymized PDF for author-identity strings. A
      # double-blind entry (submission, and the separately-submitted anonymized
      # appendix) must carry no author name, institution, email, or
      # self-referencing arXiv id (this paper's own id is 2606.22908) in its
      # rendered text. Lines matching an entry in `identityExceptions` are
      # carved out before the scan, for deliberately-permitted third-person
      # self-citations. Fail-closed: any surviving identity string aborts the
      # build.
      identityLeakScan = { entry, identityExceptions }: ''
        pdftotext -layout ${entry}.pdf anon-scan.txt
        ${lib.concatMapStrings (pattern: ''
          grep -v -F ${lib.escapeShellArg pattern} anon-scan.txt > anon-scan.tmp || true
          mv anon-scan.tmp anon-scan.txt
        '') identityExceptions}
        anonLeak=0
        for needle in "Bo Yang" "yang-bo" "Figure AI" "Atry" "2606.22908"; do
          if grep -i -F "$needle" anon-scan.txt > /dev/null; then
            echo "FAIL: identity leak '$needle' in anonymized ${entry}.pdf" >&2
            grep -i -F -n "$needle" anon-scan.txt >&2 || true
            anonLeak=1
          fi
        done
        if [ "$anonLeak" -ne 0 ]; then exit 1; fi
      '';

      mkPaperPdf = { name, root, fileset, entry ? "supplement", anonymous ? false, identityExceptions ? [] }:
        pkgs.stdenv.mkDerivation {
          inherit name;
          src = lib.fileset.toSource { inherit root fileset; };
          nativeBuildInputs = [ paperTexlive ]
            ++ lib.optionals anonymous [ pkgs.poppler-utils ];
          # Reproducible PDF: fix the timestamp pdftex embeds.
          SOURCE_DATE_EPOCH = "1";
          buildPhase = ''
            runHook preBuild
            export HOME=$TMPDIR
            export TEXMFVAR=$TMPDIR/texmf-var
            latexmk -pdf -interaction=nonstopmode -halt-on-error ${entry}.tex
            ${lib.optionalString anonymous (identityLeakScan { inherit entry identityExceptions; })}
            runHook postBuild
          '';
          installPhase = ''
            runHook preInstall
            cp ${entry}.pdf $out
            runHook postInstall
          '';
        };

      tablambdaSources = lib.fileset.unions [
        ../paper/tablambda.tex
        ../paper/supplement.tex
        ../paper/supplement-xref.tex
        ../paper/submission.tex
        ../paper/preprint.tex
        ../paper/preprint-zh.tex
        # The LNCS entry for FLOPS, and the ACM CCS block the acmart entries
        # \input (kept in its own file because the comment package cannot read
        # a CCSXML environment from inside a TeX conditional).
        ../paper/flops.tex
        ../paper/ccs-concepts.tex
        # \input by submission.tex and supplement.tex (drops acmart's tocindent
        # labels when importing the cross-document .aux via xr-hyper).
        ../paper/xr-tocindent-filter.tex
        ../paper/acmart.cls
        ../paper/ACM-Reference-Format.bst
        ../paper/references.bib
        ../paper/latexmkrc
        ../paper/generated
      ];

      tablambdaAppendixPdf = mkPaperPdf {
        name = "tablambda-appendix.pdf";
        root = ../paper;
        fileset = tablambdaSources;
        anonymous = true;
      };

      tablambdaSubmissionPdf = mkPaperPdf {
        name = "tablambda-submission.pdf";
        root = ../paper;
        fileset = tablambdaSources;
        entry = "submission";
        anonymous = true;
      };

      # The FLOPS submission: Springer LNCS, single-blind, the appendix following
      # the references in the same PDF.
      tablambdaFlopsPdf = mkPaperPdf {
        name = "tablambda-flops.pdf";
        root = ../paper;
        fileset = tablambdaSources;
        entry = "flops";
      };

      # The Chinese preprint: the same full document as the English preprint with
      # reader-facing prose in Chinese, built with pdfLaTeX via CJKutf8.
      tablambdaPreprintZhPdf = mkPaperPdf {
        name = "tablambda-preprint-zh.pdf";
        root = ../paper;
        fileset = tablambdaSources;
        entry = "preprint-zh";
      };

      tablambdaSrc = lib.fileset.toSource {
        root = ../paper;
        fileset = tablambdaSources;
      };

      # The arxiv submission bundle: build preprint.pdf, then tar the exact set of
      # source files latexmk recorded as inputs (from preprint.fls), dropping generated
      # outputs and .bbl and adding the .bib files. A buildable artifact so the
      # subproject owns its packaging logic.
      tablambdaArxiv = pkgs.stdenv.mkDerivation {
        name = "tablambda-arxiv-submission.tar.gz";
        src = tablambdaSrc;
        nativeBuildInputs = [ paperTexlive pkgs.gnutar pkgs.gawk pkgs.gzip ];
        SOURCE_DATE_EPOCH = "1";
        buildPhase = ''
          runHook preBuild
          export HOME=$TMPDIR
          export TEXMFVAR=$TMPDIR/texmf-var
          latexmk -pdf -interaction=nonstopmode -halt-on-error preprint.tex
          tar -czf "$TMPDIR/arxiv-submission.tar.gz" \
            -C . \
            $(gawk '
              NR==1 && /^PWD /{pwd=$2 "/"; next}
              /^OUTPUT /{gsub(/^OUTPUT \.\//, "OUTPUT "); outputs[$2]=1; next}
              /^INPUT /{
                sub(/^INPUT \.\//, "INPUT ");
                path=$2;
                if (path ~ /^\//) {
                  if (index(path, pwd)==1) path=substr(path, length(pwd)+1);
                  else next;
                }
                inputs[path]=1;
              }
              END{for (f in inputs) if (!(f in outputs) && f !~ /\.bbl$/) print f}
            ' preprint.fls | sort -u) \
            *.bib
          runHook postBuild
        '';
        installPhase = ''
          runHook preInstall
          cp "$TMPDIR/arxiv-submission.tar.gz" $out
          runHook postInstall
        '';
      };
    in {
      tablambdaTexlivePackages = texlivePackages;
      packages.tablambda-appendix = tablambdaAppendixPdf;
      packages.tablambda-submission = tablambdaSubmissionPdf;
      packages.tablambda-flops = tablambdaFlopsPdf;
      packages.tablambda-preprint-zh = tablambdaPreprintZhPdf;
      packages.tablambda-arxiv = tablambdaArxiv;
    };
}
