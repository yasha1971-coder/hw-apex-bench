/* Mechanical extraction from published main; deliberately included at call sites.
   This is a temporary source layout, not an adapter ABI. No include guard. */
#if HWAPEX_EXTRACT_SECTION == 1

        /* Pinned ACEPX2 header, little endian; source reconstruction span is
           derived from the actual archive, not from the requested block setting. */
        if(an<68 || memcmp(arc,"ACEPX2\0\0",8)) die("ACEPX2 header");
        memcpy(&original,arc+12,8); memcpy(&block,arc+20,4);
        if(!block||original!=fn) die("ACEPX2 geometry");

#elif HWAPEX_EXTRACT_SECTION == 2

            double t0=now();
            int64_t r=aceapex_decompress_region(arc,an,raw,LENGTH,start,span);
            elapsed=(now()-t0)*1000;
            if(r!=LENGTH) die("ACEAPEX region");

#elif HWAPEX_EXTRACT_SECTION == 3
    return aceapex_decompress_region(c->arc,c->archive_size,dst,len,off,len);
#elif HWAPEX_EXTRACT_SECTION == 4
    return aceapex_decompress(c->arc,c->archive_size,dst,c->size);
#elif HWAPEX_EXTRACT_SECTION == 5
        if(aceapex_decompress_ranges(c.arc,c.archive_size,ranges,(size_t)w,threads)!=w) cb_die("native warmup");

#elif HWAPEX_EXTRACT_SECTION == 6
                ok=aceapex_decompress_ranges(c.arc,c.archive_size,ranges,(size_t)n,threads);

#else
#error "unknown native extraction section"
#endif
