import { useState } from 'react';
import axios from 'axios';
import { Tree } from 'react-arborist';
import { ReactFlow, Background, Controls, MiniMap, BackgroundVariant } from '@xyflow/react';
import type { Node as RFNode, Edge as RFEdge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Upload, FolderTree, BrainCircuit, Network, AlertTriangle, Zap, Loader2 } from 'lucide-react';

// Types
interface TreeNode {
  id: string;
  name: string;
  children?: TreeNode[];
}

interface Analysis {
  metrics: {
    nodes_count: number;
    topics_count: number;
    publishers_count: number;
    subscribers_count: number;
    services_count: number;
    parameters_count: number;
  };
  behavior_summary: string;
  warnings: string[];
}

interface GraphData {
  nodes: RFNode[];
  edges: RFEdge[];
}

type TabId = 'upload' | 'tree' | 'analysis' | 'graph';

interface TabConfig {
  id: TabId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

// Helpers
function convertToArboristFormat(node: any, parentPath = ''): TreeNode {
  const currentPath = parentPath ? `${parentPath}/${node.name}` : node.name;

  const arboristNode: TreeNode = {
    id: currentPath,
    name: node.name,
  };

  if (node.children && node.children.length > 0) {
    arboristNode.children = node.children.map((child: any) =>
      convertToArboristFormat(child, currentPath)
    );
  }

  return arboristNode;
}

function layoutGraph(nodes: any[], edges: any[]): { nodes: RFNode[]; edges: RFEdge[] } {
  const nodeMap = new Map<string, { x: number; y: number }>();

  const rosNodes = nodes.filter((n: any) => n.type === 'node');
  const topics = nodes.filter((n: any) => n.type === 'topic');

  rosNodes.forEach((node: any, i: number) => {
    nodeMap.set(node.id, { x: 100, y: 100 + i * 150 });
  });

  topics.forEach((topic: any, i: number) => {
    nodeMap.set(topic.id, { x: 500, y: 100 + i * 150 });
  });

  const layoutedNodes: RFNode[] = nodes.map((node: any) => {
    const pos = nodeMap.get(node.id) || { x: 0, y: 0 };
    return {
      id: node.id,
      type: 'default',
      position: pos,
      data: { label: node.label },
      style: {
        background: node.type === 'node' ? '#3b82f6' : '#10b981',
        color: 'white',
        border: '2px solid #1e40af',
        borderRadius: '8px',
        padding: '10px',
        fontSize: '14px',
        fontWeight: 'bold',
      },
    };
  });

  const layoutedEdges: RFEdge[] = edges.map((edge: any) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label,
    animated: true,
    style: { stroke: '#64748b', strokeWidth: 2 },
    labelStyle: { fill: '#64748b', fontWeight: 600 },
  }));

  return { nodes: layoutedNodes, edges: layoutedEdges };
}

// Main App
function App() {
  const [activeTab, setActiveTab] = useState<TabId>('upload');
  const [treeData, setTreeData] = useState<TreeNode[] | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
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
      console.log('[UPLOAD] Analysis ID:', id);

      const [treeRes, anaRes, graphRes] = await Promise.all([
        axios.get(`http://localhost:8000/api/project-tree/${id}`),
        axios.get(`http://localhost:8000/api/analyze/${id}`),
        axios.get(`http://localhost:8000/api/graph/${id}`),
      ]);

      console.log('[TREE RESPONSE]', treeRes.data);
      console.log('[ANALYSIS RESPONSE]', JSON.stringify(anaRes.data, null, 2));
      console.log('[GRAPH RESPONSE]', graphRes.data);

      if (treeRes.data.tree) {
        const converted = convertToArboristFormat(treeRes.data.tree);
        setTreeData([converted]);
      }

      setAnalysis(anaRes.data);

      if (graphRes.data?.nodes?.length && graphRes.data?.edges?.length) {
        const layouted = layoutGraph(graphRes.data.nodes, graphRes.data.edges);
        setGraph(layouted);
      }

      setActiveTab('analysis');
    } catch (err: any) {
      console.error('[ERROR]', err);
      setError(err.response?.data?.detail || err.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const tabs: TabConfig[] = [
    { id: 'upload', label: 'Upload Project', icon: Upload },
    { id: 'tree', label: 'File Tree', icon: FolderTree },
    { id: 'analysis', label: 'Analysis', icon: BrainCircuit },
    { id: 'graph', label: 'Communication Graph', icon: Network },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 to-indigo-950 text-gray-100">
      {/* Header - Centré */}
      <header className="bg-black/80 backdrop-blur-xl border-b border-cyan-500/30 shadow-xl">
        <div className="max-w-7xl mx-auto px-6 py-6 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Zap className="w-10 h-10 text-cyan-400 animate-pulse" />
            <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-purple-500 bg-clip-text text-transparent">
              ROS Intelligence Hub
            </h1>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
            <span>Online • ROS 1 Analyzer</span>
          </div>
        </div>
      </header>

      <div className="flex h-[calc(100vh-96px)] max-w-[1920px] mx-auto">
        {/* Sidebar - Largeur fixe */}
        <div className="w-64 bg-black/70 backdrop-blur-lg border-r border-cyan-500/20 p-6 flex flex-col gap-4">
          <h2 className="text-xl font-bold text-cyan-400 mb-6">Navigation</h2>
          {tabs.map(tab => {
            const IconComponent = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-3 p-4 rounded-xl transition-all ${
                  activeTab === tab.id
                    ? 'bg-gradient-to-r from-cyan-600/40 to-purple-600/40 border-l-4 border-cyan-400 text-white shadow-md'
                    : 'hover:bg-gray-800/50 text-gray-300'
                }`}
              >
                <IconComponent className="w-6 h-6" />
                {tab.label}
              </button>
            );
          })}

          {/* Debug Info */}
          <div className="mt-auto pt-4 border-t border-gray-700 text-xs text-gray-500">
            <p>Tree: {treeData ? '✓' : '✗'}</p>
            <p>Analysis: {analysis ? '✓' : '✗'}</p>
            <p>Graph: {graph.nodes.length} nodes, {graph.edges.length} edges</p>
          </div>
        </div>

        {/* Main Content - Centré avec max-width */}
        <main className="flex-1 overflow-auto">
          <div className="max-w-6xl mx-auto px-8 py-8">
            {loading && (
              <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
                <div className="text-center">
                  <Loader2 className="w-16 h-16 text-cyan-400 animate-spin mx-auto mb-4" />
                  <p className="text-xl text-cyan-300">Analyzing ROS Package...</p>
                </div>
              </div>
            )}

            {error && (
              <div className="bg-red-900/60 border border-red-500 text-red-100 p-6 rounded-xl mb-8">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-6 h-6" />
                  <span>{error}</span>
                </div>
              </div>
            )}

            {activeTab === 'upload' && (
              <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
                <div className="w-full max-w-3xl">
                  <h2 className="text-4xl font-bold text-center mb-12 text-cyan-300">
                    Upload Your ROS Project
                  </h2>

                  <label className="block cursor-pointer">
                    <div className="border-4 border-dashed border-cyan-500/50 rounded-3xl p-20 text-center hover:border-cyan-400 transition-all hover:shadow-[0_0_30px_rgba(6,182,212,0.3)]">
                      <input type="file" accept=".zip" onChange={handleUpload} className="hidden" />
                      <Upload className="w-24 h-24 text-cyan-400 mx-auto mb-6" />
                      <p className="text-2xl font-bold text-cyan-300 mb-4">
                        Drag & Drop or Click to Upload ZIP
                      </p>
                      <p className="text-gray-400">ROS 1 packages only • Max 100MB</p>
                    </div>
                  </label>
                </div>
              </div>
            )}

            {activeTab === 'tree' && treeData && treeData.length > 0 && (
              <div>
                <h2 className="text-3xl font-bold mb-8 text-cyan-300 text-center">Project Structure</h2>
                <div className="bg-black/60 rounded-2xl p-6 border border-cyan-500/20">
                  <div className="h-[70vh] overflow-auto">
                    <Tree
                      data={treeData}
                      openByDefault={true}
                      width="100%"
                      height={600}
                      indent={24}
                      rowHeight={32}
                    >
                      {(props: {
                        node: { isLeaf: boolean; isOpen: boolean; data: { name: string } };
                        style: React.CSSProperties;
                        dragHandle: React.Ref<HTMLDivElement> | undefined;
                      }) => (
                        <div
                          style={props.style}
                          ref={props.dragHandle}
                          className="flex items-center gap-2 text-gray-200 hover:text-cyan-300 cursor-pointer"
                        >
                          <span>{props.node.isLeaf ? '📄' : props.node.isOpen ? '📂' : '📁'}</span>
                          <span>{props.node.data.name}</span>
                        </div>
                      )}
                    </Tree>
                  </div>

                  <details className="mt-4 text-xs">
                    <summary className="text-gray-500 cursor-pointer">Debug: Raw Tree Data</summary>
                    <pre className="text-gray-400 overflow-auto max-h-40 mt-2">
                      {JSON.stringify(treeData, null, 2)}
                    </pre>
                  </details>
                </div>
              </div>
            )}

            {activeTab === 'tree' && (!treeData || treeData.length === 0) && (
              <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
                <div className="text-center">
                  <FolderTree className="w-24 h-24 text-gray-600 mx-auto mb-6" />
                  <p className="text-xl text-gray-400">No project uploaded yet</p>
                  <p className="text-gray-500 mt-2">Upload a ZIP file to see the project structure</p>
                </div>
              </div>
            )}

            {activeTab === 'analysis' && analysis && (
              <div>
                <h2 className="text-3xl font-bold mb-8 text-cyan-300 text-center">Analysis Results</h2>

                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-10">
                  <div className="bg-gradient-to-br from-cyan-900/80 to-cyan-700/80 p-6 rounded-2xl shadow-lg border border-cyan-500/30 text-center hover:scale-105 transition-transform">
                    <p className="text-lg text-cyan-200 mb-1">Nodes</p>
                    <p className="text-5xl font-bold text-white">{analysis.metrics.nodes_count}</p>
                  </div>
                  <div className="bg-gradient-to-br from-purple-900/80 to-purple-700/80 p-6 rounded-2xl shadow-lg border border-purple-500/30 text-center hover:scale-105 transition-transform">
                    <p className="text-lg text-purple-200 mb-1">Topics</p>
                    <p className="text-5xl font-bold text-white">{analysis.metrics.topics_count}</p>
                  </div>
                  <div className="bg-gradient-to-br from-green-900/80 to-green-700/80 p-6 rounded-2xl shadow-lg border border-green-500/30 text-center hover:scale-105 transition-transform">
                    <p className="text-lg text-green-200 mb-1">Publishers</p>
                    <p className="text-5xl font-bold text-white">{analysis.metrics.publishers_count}</p>
                  </div>
                  <div className="bg-gradient-to-br from-red-900/80 to-red-700/80 p-6 rounded-2xl shadow-lg border border-red-500/30 text-center hover:scale-105 transition-transform">
                    <p className="text-lg text-red-200 mb-1">Subscribers</p>
                    <p className="text-5xl font-bold text-white">{analysis.metrics.subscribers_count}</p>
                  </div>
                  <div className="bg-gradient-to-br from-indigo-900/80 to-indigo-700/80 p-6 rounded-2xl shadow-lg border border-indigo-500/30 text-center hover:scale-105 transition-transform">
                    <p className="text-lg text-indigo-200 mb-1">Services</p>
                    <p className="text-5xl font-bold text-white">{analysis.metrics.services_count ?? 0}</p>
                  </div>
                  <div className="bg-gradient-to-br from-amber-900/80 to-amber-700/80 p-6 rounded-2xl shadow-lg border border-amber-500/30 text-center hover:scale-105 transition-transform">
                    <p className="text-lg text-amber-200 mb-1">Parameters</p>
                    <p className="text-5xl font-bold text-white">{analysis.metrics.parameters_count ?? 0}</p>
                  </div>
                </div>

                <div className="bg-black/60 rounded-2xl p-8 border border-cyan-500/20 mb-10">
                  <h3 className="text-2xl font-bold text-cyan-300 mb-4 flex items-center gap-3">
                    <BrainCircuit className="w-7 h-7" />
                    Behavior Summary
                  </h3>
                  <p className="text-gray-200 leading-relaxed whitespace-pre-wrap">
                    {analysis.behavior_summary || 'No behavior summary available.'}
                  </p>
                </div>

                {analysis.warnings?.length > 0 && (
                  <div className="bg-amber-950/50 border border-amber-500/30 rounded-2xl p-8">
                    <h3 className="text-2xl font-bold text-amber-300 mb-4 flex items-center gap-3">
                      <AlertTriangle className="w-7 h-7" />
                      Warnings & Best Practices
                    </h3>
                    <ul className="space-y-4 text-amber-100">
                      {analysis.warnings.map((warning: string, index: number) => (
                        <li key={index} className="flex items-start gap-4">
                          <AlertTriangle className="w-6 h-6 mt-1 flex-shrink-0" />
                          {warning}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'analysis' && !analysis && (
              <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
                <div className="text-center">
                  <BrainCircuit className="w-24 h-24 text-gray-600 mx-auto mb-6" />
                  <p className="text-xl text-gray-400">No analysis available</p>
                  <p className="text-gray-500 mt-2">Upload a ZIP file to see the analysis</p>
                </div>
              </div>
            )}

            {activeTab === 'graph' && graph.nodes.length > 0 && (
              <div>
                <h2 className="text-3xl font-bold mb-8 text-cyan-300 text-center">Communication Graph</h2>
                <div className="bg-black/60 rounded-2xl border border-cyan-500/20 overflow-hidden">
                  <div className="h-[75vh]">
                    <ReactFlow
                      nodes={graph.nodes}
                      edges={graph.edges}
                      fitView
                      minZoom={0.2}
                      maxZoom={2}
                    >
                      <Background variant={BackgroundVariant.Dots} />
                      <Controls />
                      <MiniMap />
                    </ReactFlow>
                  </div>

                  <details className="p-4 text-xs border-t border-gray-700">
                    <summary className="text-gray-500 cursor-pointer">Debug: Graph Data</summary>
                    <div className="mt-2 space-y-2">
                      <div>
                        <p className="text-gray-400">Nodes ({graph.nodes.length}):</p>
                        <pre className="text-gray-400 overflow-auto max-h-40">
                          {JSON.stringify(graph.nodes, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <p className="text-gray-400">Edges ({graph.edges.length}):</p>
                        <pre className="text-gray-400 overflow-auto max-h-40">
                          {JSON.stringify(graph.edges, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </details>
                </div>
              </div>
            )}

            {activeTab === 'graph' && graph.nodes.length === 0 && (
              <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
                <div className="text-center">
                  <Network className="w-24 h-24 text-gray-600 mx-auto mb-6" />
                  <p className="text-xl text-gray-400">No graph data available</p>
                  <p className="text-gray-500 mt-2">Upload a ZIP file to see the communication graph</p>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;