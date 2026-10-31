MATCH (w:Warga)
RETURN count(w) AS warga, count(w.komunitas) AS punya_komunitas,
       count(DISTINCT w.komunitas) AS jumlah_komunitas, count(w.pagerank) AS punya_pagerank;

MATCH (w:Warga)
OPTIONAL MATCH (w)-[r:MENJAMIN|PERNAH_MEMINJAM_DARI]->(v:Warga)
RETURN w, r, v;
