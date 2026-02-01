import { useState } from 'react';
import axios from 'axios';
import { Tree } from 'react-arborist';
import { ReactFlow, Background, Controls, MiniMap, BackgroundVariant } from '@xyflow/react';
import type { Node as RFNode, Edge as RFEdge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Upload, FolderTree, BrainCircuit, Network, AlertTriangle, Zap, Loader2, CheckCircle2, ChevronRight } from 'lucide-react';

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
  step: number;
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
  const [uploadComplete, setUploadComplete] = useState(false);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);
    setUploadComplete(false);

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

      setUploadComplete(true);
      setActiveTab('tree');
    } catch (err: any) {
      console.error('[ERROR]', err);
      setError(err.response?.data?.detail || err.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const tabs: TabConfig[] = [
    { id: 'upload', label: 'Upload', icon: Upload, step: 1 },
    { id: 'tree', label: 'File Tree', icon: FolderTree, step: 2 },
    { id: 'analysis', label: 'Analysis', icon: BrainCircuit, step: 3 },
    { id: 'graph', label: 'Graph', icon: Network, step: 4 },
  ];

  const getCurrentStep = () => {
    const currentTab = tabs.find(t => t.id === activeTab);
    return currentTab ? currentTab.step : 1;
  };

  const isTabEnabled = (tabId: TabId) => {
    if (tabId === 'upload') return true;
    return uploadComplete;
  };

  return (
    <div className="h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-gray-100 flex flex-col overflow-hidden">
      {/* Compact Header */}
      <header className="flex-shrink-0 bg-slate-900/95 backdrop-blur-xl border-b border-cyan-500/20 shadow-2xl">
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Zap className="w-7 h-7 text-cyan-400" />
            <h1 className="text-xl font-bold text-white">
              ROS Intelligence Hub
            </h1>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="px-3 py-1.5 bg-cyan-500/10 border border-cyan-500/30 rounded-lg backdrop-blur-sm">
              <span className="text-cyan-300 font-semibold text-sm">
                Step {getCurrentStep()}/4
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-gray-300 text-sm">Online</span>
            </div>
          </div>
        </div>
        
        {/* Thin Progress Bar */}
        <div className="h-0.5 bg-slate-800">
          <div 
            className="h-full bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-500 transition-all duration-700 ease-out shadow-lg shadow-cyan-500/50"
            style={{ width: `${(getCurrentStep() / 4) * 100}%` }}
          />
        </div>
      </header>

      {/* Main Content - Flex Row */}
      <div className="flex-1 flex overflow-hidden">
        {/* Compact Sidebar */}
        <aside className="w-52 flex-shrink-0 bg-slate-900/80 backdrop-blur-lg border-r border-slate-700/50">
          <div className="h-full flex flex-col p-4">
            {/* Navigation */}
            <nav className="flex-1 space-y-1.5">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                const enabled = isTabEnabled(tab.id);
                const isCompleted = uploadComplete && tab.step < getCurrentStep();

                return (
                  <button
                    key={tab.id}
                    onClick={() => enabled && setActiveTab(tab.id)}
                    disabled={!enabled}
                    className={`
                      w-full group relative flex items-center gap-2.5 px-3 py-2.5 rounded-lg transition-all duration-300
                      ${isActive 
                        ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 border border-cyan-400/50 text-cyan-300 shadow-lg shadow-cyan-500/20' 
                        : enabled
                          ? 'hover:bg-slate-800/60 text-gray-400 hover:text-cyan-300 border border-transparent hover:border-slate-700'
                          : 'opacity-30 cursor-not-allowed text-gray-600 border border-transparent'
                      }
                    `}
                  >
                    {/* Step Number Badge */}
                    <div className={`
                      flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
                      ${isActive 
                        ? 'bg-cyan-500/30 text-cyan-300' 
                        : isCompleted
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-slate-800 text-gray-500'
                      }
                    `}>
                      {isCompleted ? <CheckCircle2 className="w-3.5 h-3.5" /> : tab.step}
                    </div>
                    
                    <Icon className={`w-4 h-4 flex-shrink-0 ${isActive ? 'text-cyan-400' : ''}`} />
                    
                    <span className={`text-sm font-medium flex-1 text-left ${isActive ? 'text-cyan-300' : ''}`}>
                      {tab.label}
                    </span>
                    
                    {isActive && (
                      <ChevronRight className="w-4 h-4 text-cyan-400 animate-pulse" />
                    )}
                  </button>
                );
              })}
            </nav>

            {/* Status Card */}
            {uploadComplete && (
              <div className="mt-auto p-3 bg-gradient-to-br from-green-500/10 to-emerald-500/10 border border-green-500/30 rounded-lg backdrop-blur-sm">
                <div className="flex items-center gap-2 text-green-400 text-xs mb-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span className="font-semibold">Project Loaded</span>
                </div>
                <p className="text-xs text-gray-400">Ready to explore</p>
              </div>
            )}
          </div>
        </aside>

        {/* Main Content Area - Full Height */}
        <main className="flex-1 overflow-y-auto">
          <div className="h-full px-8 py-6">
            {/* Error Display */}
            {error && (
              <div className="mb-6 p-5 bg-red-950/50 border border-red-500/30 rounded-xl animate-in slide-in-from-top">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="text-base font-bold text-red-300 mb-1">Upload Error</h3>
                    <p className="text-sm text-red-200">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Loading Overlay */}
            {loading && (
              <div className="mb-6 p-6 bg-cyan-950/50 border border-cyan-500/30 rounded-xl animate-pulse">
                <div className="flex items-center gap-3">
                  <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
                  <div>
                    <p className="text-base font-semibold text-cyan-300">Processing your project...</p>
                    <p className="text-xs text-gray-400 mt-0.5">Analyzing ROS nodes and communication flows</p>
                  </div>
                </div>
              </div>
            )}

            {/* Tab Content */}
            <div className="h-full">
              {/* Upload Tab */}
              {activeTab === 'upload' && (
                <div className="h-full flex items-center justify-center animate-in fade-in slide-in-from-bottom duration-500">
                  <div className="max-w-3xl w-full">
                    <div className="text-center mb-6">
                      <h2 className="text-3xl font-bold mb-2 text-white">
                        Upload Your ROS Project
                      </h2>
                      <p className="text-gray-400">Drop your ZIP file below to start the analysis</p>
                    </div>

                    <label className="block cursor-pointer group">
                      <div className="relative bg-gradient-to-br from-slate-900/90 to-slate-800/90 border-2 border-dashed border-cyan-500/40 rounded-2xl p-20 text-center transition-all duration-300 hover:border-cyan-400/80 hover:bg-slate-900/50 hover:shadow-2xl hover:shadow-cyan-500/20 backdrop-blur-xl">
                        <input type="file" accept=".zip" onChange={handleUpload} className="hidden" />
                        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-blue-500/5 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                        <Upload className="relative w-20 h-20 text-cyan-400 mx-auto mb-5 group-hover:scale-110 transition-transform duration-300" />
                        <p className="relative text-xl font-bold text-cyan-300 mb-2">
                          Drag & Drop or Click to Upload
                        </p>
                        <p className="relative text-sm text-gray-400">ROS 1 packages • ZIP format • Max 100MB</p>
                      </div>
                    </label>

                    {/* Quick Steps */}
                    <div className="grid grid-cols-3 gap-3 mt-6">
                      {['Upload ZIP', 'Auto Analysis', 'View Results'].map((text, i) => (
                        <div key={i} className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-3 text-center backdrop-blur-sm">
                          <div className={`
                            w-8 h-8 rounded-full flex items-center justify-center mx-auto mb-2 text-sm font-bold
                            ${i === 0 ? 'bg-cyan-500/20 text-cyan-400' : i === 1 ? 'bg-purple-500/20 text-purple-400' : 'bg-green-500/20 text-green-400'}
                          `}>
                            {i + 1}
                          </div>
                          <p className="text-xs text-gray-300">{text}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* File Tree Tab */}
              {activeTab === 'tree' && (
                <div className="h-full animate-in fade-in slide-in-from-bottom duration-500">
                  {treeData && treeData.length > 0 ? (
                    <div className="h-full flex flex-col">
                      <div className="text-center mb-5">
                        <h2 className="text-3xl font-bold mb-2 text-white">
                          Project Structure
                        </h2>
                        <p className="text-gray-400 text-sm">Explore your ROS package hierarchy</p>
                      </div>

                      <div className="flex-1 bg-slate-900/60 rounded-xl border border-slate-700/50 overflow-hidden backdrop-blur-sm">
                        <div className="h-full p-4">
                          <div className="h-full overflow-auto rounded-lg bg-slate-950/50 p-3">
                            <Tree
                              data={treeData}
                              openByDefault={true}
                              width="100%"
                              height={600}
                              indent={20}
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
                                  className="flex items-center gap-2.5 text-gray-300 hover:text-cyan-300 hover:bg-cyan-500/10 px-2.5 py-1 rounded-md cursor-pointer transition-all duration-200"
                                >
                                  <span className="text-base">
                                    {props.node.isLeaf ? '📄' : props.node.isOpen ? '📂' : '📁'}
                                  </span>
                                  <span className="text-sm font-medium">{props.node.data.name}</span>
                                </div>
                              )}
                            </Tree>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="h-full flex items-center justify-center">
                      <div className="text-center">
                        <FolderTree className="w-20 h-20 text-slate-600 mx-auto mb-4 opacity-50" />
                        <p className="text-xl text-gray-400 mb-1">No project uploaded</p>
                        <p className="text-sm text-gray-500">Upload a ZIP file to see the structure</p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Analysis Tab */}
              {activeTab === 'analysis' && (
                <div className="h-full overflow-y-auto animate-in fade-in slide-in-from-bottom duration-500">
                  {analysis ? (
                    <div className="pb-6">
                      <div className="text-center mb-5">
                        <h2 className="text-3xl font-bold mb-2 text-white">
                          Analysis Results
                        </h2>
                        <p className="text-gray-400 text-sm">Comprehensive ROS metrics and insights</p>
                      </div>

                      {/* Compact Metrics Grid */}
                      <div className="grid grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
                        {[
                          { label: 'Nodes', value: analysis.metrics.nodes_count, color: 'cyan' },
                          { label: 'Topics', value: analysis.metrics.topics_count, color: 'purple' },
                          { label: 'Publishers', value: analysis.metrics.publishers_count, color: 'green' },
                          { label: 'Subscribers', value: analysis.metrics.subscribers_count, color: 'red' },
                          { label: 'Services', value: analysis.metrics.services_count ?? 0, color: 'indigo' },
                          { label: 'Parameters', value: analysis.metrics.parameters_count ?? 0, color: 'amber' },
                        ].map((metric, i) => (
                          <div key={i} className={`
                            bg-gradient-to-br from-${metric.color}-900/60 to-${metric.color}-800/60 
                            p-4 rounded-xl border border-${metric.color}-500/30 text-center 
                            hover:scale-105 transition-transform duration-300 backdrop-blur-sm
                          `}>
                            <p className="text-xs text-gray-300 mb-1.5 uppercase tracking-wider font-semibold">{metric.label}</p>
                            <p className="text-4xl font-bold text-white">{metric.value}</p>
                          </div>
                        ))}
                      </div>

                      {/* Behavior Summary */}
                      <div className="bg-slate-900/60 rounded-xl p-6 border border-slate-700/50 mb-6 backdrop-blur-sm">
                        <h3 className="text-lg font-bold text-cyan-300 mb-3 flex items-center gap-2">
                          <BrainCircuit className="w-5 h-5" />
                          Behavior Summary
                        </h3>
                        <p className="text-gray-200 leading-relaxed text-sm whitespace-pre-wrap">
                          {analysis.behavior_summary || 'No behavior summary available.'}
                        </p>
                      </div>

                      {/* Warnings */}
                      {analysis.warnings?.length > 0 && (
                        <div className="bg-amber-950/40 border border-amber-500/30 rounded-xl p-6 backdrop-blur-sm">
                          <h3 className="text-lg font-bold text-amber-300 mb-4 flex items-center gap-2">
                            <AlertTriangle className="w-5 h-5" />
                            Warnings & Best Practices
                          </h3>
                          <ul className="space-y-3">
                            {analysis.warnings.map((warning: string, index: number) => (
                              <li key={index} className="flex items-start gap-3 text-amber-100 bg-amber-950/30 p-3 rounded-lg text-sm">
                                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-400" />
                                <span>{warning}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="h-full flex items-center justify-center">
                      <div className="text-center">
                        <BrainCircuit className="w-20 h-20 text-slate-600 mx-auto mb-4 opacity-50" />
                        <p className="text-xl text-gray-400 mb-1">No analysis available</p>
                        <p className="text-sm text-gray-500">Upload a ZIP file first</p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Graph Tab */}
              {activeTab === 'graph' && (
                <div className="h-full flex flex-col animate-in fade-in slide-in-from-bottom duration-500">
                  {graph.nodes.length > 0 ? (
                    <>
                      <div className="text-center mb-5">
                        <h2 className="text-3xl font-bold mb-2 text-white">
                          Communication Graph
                        </h2>
                        <p className="text-gray-400 text-sm">Visual representation of ROS node interactions</p>
                      </div>

                      <div className="flex-1 bg-slate-900/60 rounded-xl border border-slate-700/50 overflow-hidden backdrop-blur-sm">
                        <ReactFlow
                          nodes={graph.nodes}
                          edges={graph.edges}
                          fitView
                          minZoom={0.2}
                          maxZoom={2}
                        >
                          <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#1e293b" />
                          <Controls />
                          <MiniMap 
                            nodeColor={(node) => node.style?.background as string || '#3b82f6'}
                            maskColor="rgba(15, 23, 42, 0.8)"
                          />
                        </ReactFlow>
                      </div>
                    </>
                  ) : (
                    <div className="h-full flex items-center justify-center">
                      <div className="text-center">
                        <Network className="w-20 h-20 text-slate-600 mx-auto mb-4 opacity-50" />
                        <p className="text-xl text-gray-400 mb-1">No graph available</p>
                        <p className="text-sm text-gray-500">Upload a ZIP file first</p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
