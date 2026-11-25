Hypotheses (not measurements):
 H1 (source-size tier): one writer lets zstd know the frame's source size (single
    ZSTD_e_end call or pledged size), so zstd picks the parameter row for small
    sources (zstd's tiers: <=16 KiB, <=128 KiB, <=256 KiB, larger); the other
    streams with unknown size. Prediction: the difference sits in every full
    frame, frame headers differ (Frame_Content_Size present or window size), and
    it vanishes for frames > 256 KiB.
 H2 (input chunking): contrib feeds 128 KiB chunks (ZSTD_CStreamInSize) with
    ZSTD_e_continue; feeding the whole frame in one call removes the difference.
 Kill H1: headers and effective parameters identical. Kill H2: one-call feeding
 changes nothing.

Method check BEFORE the main comparison (stop if any fails):
 - positive control: compress the same 256 KiB slice twice with the same call ->
   identical bytes;
 - negative control: level 3 vs level 4 on that slice -> different bytes, and the
   tool reports it;
 - header decoder: on a frame with a known Frame_Content_Size it prints that value.

Steps:
 1. From the existing archives' seek tables, list per-frame compressed sizes of
    both writers for enwik8 L3 256 KiB: is the gap in every frame or a few?
 2. Dump the frame headers of frame 0 from both (descriptor, window, FCS).
 3. Read both writers' compression path (pyzstd 0.20.0 / its compression backend,
    zstd 1.5.7 contrib/seekable_format) and find where size, pledged size or
    flush mode is set. Record file:line.
 4. Minimal C program on one 256 KiB slice: reproduce both outputs exactly
    (sha256 of the frame equals the one in each archive).
 5. Apply the one-line change to the copy of the loser writer, re-encode the four
    affected points plus 128 KiB and 512 KiB frames on enwik8 L3 (to place the
    tier boundary), check bytes and bit-perfect decode of every archive.
 6. Report: cause, file:line, size effect by frame size, which writer's choice is
    smaller and whether it costs compression or decompression speed (single
    measured pair under the OVH-BENCH lock only if needed for that decision).

Deliver evidence/hw-gift-1c/RESULTS.md on branch hw-gift-1c, draft PR. If the
cause is in contrib/seekable_format, add a draft (not sent) of a short issue for
facebook/zstd with the one-line change and the size table.
