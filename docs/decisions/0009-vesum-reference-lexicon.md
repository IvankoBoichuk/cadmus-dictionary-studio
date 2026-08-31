# ADR-0009: VESUM as an optional versioned reference lexicon

- Status: Accepted
- Date: 2026-08-31
- Context: Cadmus Dictionary Studio
- Jira: not assigned; Jira integration was unavailable when this Draft PR was created

## Context

The pilot Cadmus dictionaries contain dialect vocabulary. Editors need to link
a digitized dialect entry to a modern Ukrainian literary lemma without
overwriting the source transcription or treating the external resource as
another OCR input dictionary.

The brown-uk/dict_uk project publishes VESUM, a large Ukrainian morphological
dictionary. Its normal `expand` build requires roughly 5 GiB of free memory and
the Gradle task explicitly configures a multi-gigabyte JVM heap. GitHub Releases
already publish the generated `dict_corp_vis.txt.bz2` artifact, whose visual
format groups each lemma with its indented word forms.

VESUM dictionary data are licensed CC BY-NC-SA 4.0, while its software is GPL.
Bundling VESUM data into Cadmus core would couple product rights and lifecycle
to an external non-commercial ShareAlike dataset.

The current Cadmus MVP has `DictionaryEntry` and repeatable `EntryField` values
but does not yet have a separate `Sense` aggregate.

## Decision

Introduce an independent `reference_lexicon` bounded module.

Cadmus does not clone or build VESUM during Docker image creation or API
startup. A one-shot worker CLI accepts an explicit release version, resolves
the release through GitHub's API, downloads `dict_corp_vis.txt.bz2`, verifies
the SHA-256 digest published for that asset, and streams decompression into the
Cadmus importer.

The importer parses the visual grouping directly. Top-level rows define lemma
identity; two-space-indented rows are word forms belonging to the current
lemma. Stable UUIDs are derived from the provider and lemma identity so a
re-import updates existing logical records. Import is atomic. Rows missing from
a later upstream snapshot are deactivated, not deleted, so confirmed mappings
retain referential integrity.

Each word form preserves three morphology layers:

1. raw `morphology` exactly as VESUM publishes it;
2. ordered `morphology_tags` containing every tag;
3. `morphology_features` containing conservative, documented grammatical
   features such as case, number, gender, animacy, aspect, voice, tense,
   person, degree, pronoun type, governed cases and qualifiers.

Unknown or future tags are stored in `other_tags` rather than discarded.

All VESUM rows are retained for research. By default, literary-standard search
filters the same non-standard tag classes excluded by VESUM's own spelling-word
generation: `bad`, `subst`, `alt`, `arch`, `slang`, `vulg`, `obsc` and
`rare`.

`lexicography` may depend on `reference_lexicon`, never the reverse. A user can
create an explicit confirmed `EntryReferenceLink` with a relation such as
`standard_equivalent`, `synonym`, `approximate_equivalent`, `hypernym` or
`related`. Standard-equivalent links reject a VESUM lemma marked non-standard.

Because the MVP has no `Sense` entity, links currently target
`DictionaryEntry`. The table is deliberately separate from entry fields so a
later migration can move semantic links to a `Sense` aggregate without changing
imported reference lemmas or word forms.

No VESUM dataset is committed to the Cadmus repository or baked into an
application Docker image.

## Consequences

- OCR `source_text` and `normalized_text` remain independent from external
  lexical normalization.
- No Java/Gradle/VESUM build is required on a Cadmus host.
- Search can resolve both VESUM lemmas and generated inflected forms.
- Matching word-form results can expose parsed morphology to the editor.
- Imported snapshots are reproducible and auditable by release version,
  release-asset URL and SHA-256 checksum.
- Existing mappings survive VESUM updates even when an upstream lemma becomes
  inactive.
- VESUM remains optional. A deployment that uses or redistributes the imported
  data must satisfy CC BY-NC-SA 4.0 or obtain separate permission.
- Commercial Cadmus deployments must not assume that VESUM data can be bundled
  without an additional licensing decision.
- Automatic semantic linking and confidence-scored model proposals remain
  future work; the current write path is manual and confirmed.
