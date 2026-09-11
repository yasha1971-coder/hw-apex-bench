/* Mechanical extraction from published main; deliberately included at call sites.
   This is a temporary source layout, not an adapter ABI. No include guard. */
#if HWAPEX_EXTRACT_SECTION == 1

        /* Copy archive to anonymous RAM-backed storage before any timed call.
           Keep one htslib handle and the .gzi index for the entire query trace. */
        fd=memfd_create("cabench-bgzf",MFD_CLOEXEC); if(fd<0) die("memfd_create");
        size_t done=0;
        while(done<an) { ssize_t n=write(fd,arc+done,an-done); if(n<=0) die("memfd write"); done+=(size_t)n; }
        if(lseek(fd,0,SEEK_SET)<0) die("memfd rewind");
        bgzf=bgzf_dopen(dup(fd),"r"); if(!bgzf) die("bgzf_dopen");
        if(bgzf_index_load(bgzf,argv[2],".gzi")) die("bgzf_index_load");
        if(counts) {
            reset_counts=(void(*)(void))dlsym(RTLD_DEFAULT,"cabench_reset");
            get_counts=(uint64_t(*)(void))dlsym(RTLD_DEFAULT,"cabench_bytes");
            if(!reset_counts||!get_counts) die("missing BGZF counters");
        }

#elif HWAPEX_EXTRACT_SECTION == 2

            double t0=now();
            int seek_rc=bgzf_useek(bgzf,(off_t)start,SEEK_SET);
            ssize_t r=bgzf_read(bgzf,raw,LENGTH);
            elapsed=(now()-t0)*1000;
            if(seek_rc!=0 || r!=LENGTH) die("BGZF region");

#elif HWAPEX_EXTRACT_SECTION == 3

        c.fd=memfd_create("cabench-bgzf",MFD_CLOEXEC); if(c.fd<0) cb_die("memfd");
        for(size_t pos=0;pos<c.archive_size;) { ssize_t n=write(c.fd,c.arc+pos,c.archive_size-pos); if(n<=0) cb_die("memfd write"); pos+=(size_t)n; }
        if(lseek(c.fd,0,SEEK_SET)<0) cb_die("memfd rewind");
        c.bgzf=bgzf_dopen(dup(c.fd),"r"); if(!c.bgzf) cb_die("bgzf open");
        if(bgzf_index_load(c.bgzf,archive,".gzi")) cb_die("bgzf index");

#elif HWAPEX_EXTRACT_SECTION == 4

        if(bgzf_useek(c->bgzf,(off_t)off,SEEK_SET)) return -1;
        return bgzf_read(c->bgzf,dst,len);

#elif HWAPEX_EXTRACT_SECTION == 5
 if(bgzf_seek(c->bgzf,0,SEEK_SET)) return -1; return bgzf_read(c->bgzf,dst,c->size);
#else
#error "unknown native extraction section"
#endif
