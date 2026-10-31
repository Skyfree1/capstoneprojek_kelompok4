CALL gds.graph.drop('pwSosial', false) YIELD graphName RETURN graphName;
CALL gds.graph.drop('pwPenjamin', false) YIELD graphName RETURN graphName;
MATCH (n:PinjamWarga) DETACH DELETE n;
MATCH (n:PinjamWarga) RETURN count(n) AS sisa;
