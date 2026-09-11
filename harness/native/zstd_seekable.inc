/* Mechanical extraction from published main; deliberately included at call sites.
   This is a temporary source layout, not an adapter ABI. No include guard. */
#if HWAPEX_EXTRACT_SECTION == 1

        seek=ZSTD_seekable_create(); if(!seek) die("seekable create");
        size_t r=ZSTD_seekable_initBuff(seek,arc,an);
        if(ZSTD_isError(r)) die(ZSTD_getErrorName(r));
#ifndef COUNT_DECODER
        if(counts) die("amplification needs instrumented binary");
#endif

#elif HWAPEX_EXTRACT_SECTION == 2

            double t0=now();
            size_t r=ZSTD_seekable_decompress(seek,raw,LENGTH,start);
            elapsed=(now()-t0)*1000;
            if(ZSTD_isError(r)||r!=LENGTH) die("zstd region");

#elif HWAPEX_EXTRACT_SECTION == 3

        c.seek=ZSTD_seekable_create(); if(!c.seek) cb_die("seekable create");
        size_t r=ZSTD_seekable_initBuff(c.seek,c.arc,c.archive_size); if(ZSTD_isError(r)) cb_die("seekable init");

#elif HWAPEX_EXTRACT_SECTION == 4
 size_t r=ZSTD_seekable_decompress(c->seek,dst,len,off); return ZSTD_isError(r)?-1:(int64_t)r;
#elif HWAPEX_EXTRACT_SECTION == 5
 size_t r=ZSTD_seekable_decompress(c->seek,dst,c->size,0); return ZSTD_isError(r)?-1:(int64_t)r;
#else
#error "unknown native extraction section"
#endif
