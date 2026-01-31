import { useState } from 'react';
import axios from 'axios';
import { Tree } from 'react-arborist';
import { ReactFlow, Background, Controls } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface AnalysisData {
  nodes: { name: string; file: string }[];
  topics: { name: string; message_type: string; publishers: string[]; subscribers: string[] }[];
  metrics: { nodes_count: number; topics_count: number; publishers_count: number; subscribers_count: number };
  behavior_summary: string;
  warnings: string[];
}

interface GraphData {
  nodes: any[];
  edges: any[];
}

function App() {
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [treeData, setTreeData] = useState<any>(null);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post('http://localhost:8000/api/upload-zip/', formData);
      const id = res.data.analysis_id;
      setAnalysisId(id);

      const treeRes = await axios.get(`http://localhost:8000/api/project-tree/${id}`);
      setTreeData(treeRes.data.tree);

      const anaRes = await axios.get(`http://localhost:8000/api/analyze/${id}`);
      setAnalysis(anaRes.data);

      const graphRes = await axios.get(`http://localhost:8000/api/graph/${id}`);
      // Positions aléatoires pour éviter superposition
      const adaptedNodes = graphRes.data.nodes.map((n: any) => ({
        ...n,
        position: { x: Math.random() * 600, y: Math.random() * 400 },
      }));
      setGraph({ nodes: adaptedNodes, edges: graphRes.data.edges });
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>ROS Code Intelligence Platform</h1>

      <div style={{ margin: '20px 0' }}>
        <input type="file" accept=".zip" onChange={handleUpload} disabled={loading} />
        {loading && <p style={{ color: '#3498db' }}>Analyse en cours...</p>}
        {error && <p style={{ color: 'red' }}>{error}</p>}
      </div>

      {analysisId && (
        <>
          <h2>ID: {analysisId}</h2>

          <h3>Arborescence fichiers</h3>
          {treeData && (
            <div style={{ height: '400px', border: '1px solid #ddd', marginBottom: '30px' }}>
              <Tree data={treeData} />
            </div>
          )}

          <h3>Résultats analyse</h3>
          {analysis && (
            <div style={{ background: '#f8f9fa', padding: '15px', borderRadius: '8px', marginBottom: '30px' }}>
              <h4>Comportement</h4>
              <pre style={{ whiteSpace: 'pre-wrap' }}>{analysis.behavior_summary}</pre>

              <h4>Métriques</h4>
              <ul>
                <li>Nœuds : {analysis.metrics.nodes_count}</li>
                <li>Topics : {analysis.metrics.topics_count}</li>
                <li>Publishers : {analysis.metrics.publishers_count}</li>
                <li>Subscribers : {analysis.metrics.subscribers_count}</li>
              </ul>

              <h4>Warnings</h4>
              {analysis.warnings.length > 0 ? (
                <ul style={{ color: '#e74c3c' }}>
                  {analysis.warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}
                </ul>
              ) : <p>Aucun warning</p>}
            </div>
          )}

          <h3>Graphe de communication</h3>
          {graph.nodes.length > 0 ? (
            <div style={{ height: '500px', border: '1px solid #ccc' }}>
              <ReactFlow nodes={graph.nodes} edges={graph.edges} fitView>
                <Background />
                <Controls />
              </ReactFlow>
            </div>
          ) : (
            <p>Chargement du graphe...</p>
          )}
        </>
      )}
    </div>
  );
}

export default App;