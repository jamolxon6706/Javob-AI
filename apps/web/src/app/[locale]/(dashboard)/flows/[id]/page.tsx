"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import ReactFlow, {
  addEdge,
  Background,
  Controls,
  MiniMap,
  useEdgesState,
  useNodesState,
  type Connection,
  type Node,
} from "reactflow";
import "reactflow/dist/style.css";
import { useTranslations } from "next-intl";
import { apiClient } from "@/lib/api-client";
import NodePanel from "@/components/flows/NodePanel";
import NodeConfigDrawer from "@/components/flows/NodeConfigDrawer";

const DEFAULT_NODES: Node[] = [
  {
    id: "trigger-1",
    type: "default",
    position: { x: 250, y: 50 },
    data: {
      label: "🚀 Trigger",
      nodeType: "trigger",
      trigger_type: "first_contact",
    },
    style: {
      background: "#7c3aed",
      color: "#fff",
      border: "none",
      borderRadius: 10,
      padding: "8px 16px",
    },
  },
];

export default function FlowEditorPage() {
  const params = useParams();
  const id = params?.id as string;
  const isNew = id === "new";
  const router = useRouter();
  const t = useTranslations("flows.editor");

  const [nodes, setNodes, onNodesChange] = useNodesState(DEFAULT_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [flowName, setFlowName] = useState("");
  const [triggerType, setTriggerType] = useState("first_contact");
  const [triggerConfig, setTriggerConfig] = useState<Record<string, unknown>>({});
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(!isNew);

  useEffect(() => {
    if (!isNew) {
      apiClient.get(`/flows/${id}`).then((r) => {
        const flow = r.data;
        setFlowName(flow.name);
        setTriggerType(flow.trigger_type);
        setTriggerConfig(flow.trigger_config || {});
        setNodes(flow.nodes.length > 0 ? flow.nodes : DEFAULT_NODES);
        setEdges(flow.edges);
        setLoading(false);
      });
    }
  }, [id, isNew, setNodes, setEdges]);

  const onConnect = useCallback(
    (connection: Connection) =>
      setEdges((eds) => addEdge({ ...connection, animated: true }, eds)),
    [setEdges]
  );

  const addNode = (type: string) => {
    const nodeId = `${type}-${Date.now()}`;
    const NODE_STYLES: Record<string, object> = {
      message: {
        background: "#0ea5e9",
        color: "#fff",
        border: "none",
        borderRadius: 10,
        padding: "8px 16px",
      },
      condition: {
        background: "#f59e0b",
        color: "#fff",
        border: "none",
        borderRadius: 10,
        padding: "8px 16px",
      },
      action: {
        background: "#8b5cf6",
        color: "#fff",
        border: "none",
        borderRadius: 10,
        padding: "8px 16px",
      },
      wait: {
        background: "#f97316",
        color: "#fff",
        border: "none",
        borderRadius: 10,
        padding: "8px 16px",
      },
      end: {
        background: "#6b7280",
        color: "#fff",
        border: "none",
        borderRadius: 10,
        padding: "8px 16px",
      },
    };
    const ICONS: Record<string, string> = {
      message: "💬",
      condition: "🔀",
      action: "⚡",
      wait: "⏱",
      end: "🏁",
    };

    const newNode: Node = {
      id: nodeId,
      type: "default",
      position: { x: 150 + Math.random() * 200, y: nodes.length * 100 + 150 },
      style: NODE_STYLES[type] || {},
      data: {
        label: `${ICONS[type] || ""} ${type}`,
        nodeType: type,
        text: "",
        action_name: "",
        variable: "",
        operator: "eq",
        value: "",
        delay_seconds: 0,
        params: {},
      },
    };
    setNodes((nds) => [...nds, newNode]);
  };

  const updateNodeData = (nodeId: string, data: Record<string, unknown>) => {
    setNodes((nds) =>
      nds.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n
      )
    );
    setSelectedNode(null);
  };

  const save = async () => {
    setSaving(true);
    const payload = {
      name: flowName || t("untitled"),
      trigger_type: triggerType,
      trigger_config: triggerConfig,
      nodes: nodes,
      edges: edges,
    };

    try {
      if (isNew) {
        await apiClient.post("/flows", payload);
      } else {
        await apiClient.put(`/flows/${id}`, payload);
      }
      router.push("/dashboard/flows");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center text-muted-foreground">
        Yuklanmoqda...
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Topbar */}
      <div className="flex items-center gap-4 px-4 py-2 border-b bg-card z-10">
        <button
          onClick={() => router.push("/dashboard/flows")}
          className="text-muted-foreground hover:text-foreground text-sm transition"
        >
          ← Orqaga
        </button>
        <input
          value={flowName}
          onChange={(e) => setFlowName(e.target.value)}
          placeholder={t("name_placeholder")}
          className="flex-1 bg-transparent text-sm font-medium outline-none border-b border-transparent focus:border-primary transition"
        />
        <select
          value={triggerType}
          onChange={(e) => setTriggerType(e.target.value)}
          className="text-xs bg-muted rounded-md px-2 py-1.5 outline-none"
        >
          <option value="first_contact">{t("trigger.first_contact")}</option>
          <option value="keyword">{t("trigger.keyword")}</option>
          <option value="action_result">{t("trigger.action_result")}</option>
        </select>
        {triggerType === "keyword" && (
          <input
            value={(triggerConfig.keywords as string[])?.join(", ") || ""}
            onChange={(e) =>
              setTriggerConfig({
                keywords: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
              })
            }
            placeholder="salom, hi, hello"
            className="text-xs bg-muted rounded-md px-2 py-1.5 outline-none w-40"
          />
        )}
        <button
          onClick={save}
          disabled={saving}
          className="bg-primary text-primary-foreground text-xs px-4 py-1.5 rounded-md disabled:opacity-50 font-medium transition hover:bg-primary/90"
        >
          {saving ? t("saving") : t("save")}
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Node palette */}
        <NodePanel onAdd={addNode} />

        {/* ReactFlow canvas */}
        <div className="flex-1 bg-muted/30">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedNode(node)}
            fitView
            deleteKeyCode="Delete"
          >
            <Background gap={20} size={1} color="#e5e7eb" />
            <Controls />
            <MiniMap
              nodeColor={(n) =>
                (n.style?.background as string) || "#e5e7eb"
              }
              maskColor="rgba(0,0,0,0.05)"
            />
          </ReactFlow>
        </div>

        {/* Config drawer */}
        {selectedNode && (
          <NodeConfigDrawer
            node={selectedNode}
            onSave={(data) => updateNodeData(selectedNode.id, data)}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
}
