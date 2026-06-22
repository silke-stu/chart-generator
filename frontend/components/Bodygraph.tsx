import { Center, Channel } from "@/types/chart";
import { LABELS } from "@/utils/constants";

interface BodygraphProps {
  centers: Center[];
  channels: Channel[];
}

export default function Bodygraph({ centers, channels }: BodygraphProps) {
  // Simplified bodygraph coordinates for the 9 centers
  const centerPositions: Record<string, { x: number; y: number; width: number; height: number }> = {
    head: { x: 200, y: 20, width: 80, height: 50 },
    ajna: { x: 200, y: 90, width: 80, height: 50 },
    throat: { x: 200, y: 170, width: 80, height: 50 },
    g: { x: 200, y: 280, width: 80, height: 80 },
    heart: { x: 100, y: 240, width: 70, height: 50 },
    sacral: { x: 200, y: 390, width: 80, height: 60 },
    spleen: { x: 100, y: 330, width: 70, height: 50 },
    solar: { x: 300, y: 330, width: 70, height: 50 },
    root: { x: 200, y: 480, width: 80, height: 50 },
  };

  // Color palette taken from the "Human Design Advisor" Canva layout:
  // white/outline = open, olive = consciously defined, beige = unconsciously
  // (Design-only) defined.
  const FILL_BY_STATE: Record<string, string> = {
    open: "#FFFFFF",
    defined: "#8C7330",
    unconscious: "#D9CDB0",
  };

  const STROKE_BY_STATE: Record<string, string> = {
    open: "#C7C7C7",
    defined: "#8C7330",
    unconscious: "#C9B98E",
  };

  const getCenter = (code: string) => centers.find((c) => c.code === code);

  const getCenterFill = (code: string): string => {
    const center = getCenter(code);
    return FILL_BY_STATE[center?.definitionType ?? "open"];
  };

  const getCenterStroke = (code: string): string => {
    const center = getCenter(code);
    return STROKE_BY_STATE[center?.definitionType ?? "open"];
  };

  return (
    <div className="p-6 bg-white rounded-lg shadow-md">
      <h3 className="text-xl font-semibold text-primary mb-4">{LABELS.bodygraph}</h3>
      <div className="flex justify-center">
        <svg
          viewBox="0 0 480 580"
          className="w-full max-w-md"
          style={{ maxHeight: "600px" }}
        >
          {/* Draw channels (connections between centers) */}
          {channels.map((channel, index) => {
            // Simple channel rendering - would need actual gate-to-gate mapping
            return (
              <line
                key={index}
                x1={240}
                y1={100 + index * 50}
                x2={240}
                y2={150 + index * 50}
                stroke="#B0AFA9"
                strokeWidth="3"
                opacity="0.6"
              />
            );
          })}

          {/* Head Center - Triangle */}
          <polygon
            points={`${centerPositions.head.x},${centerPositions.head.y + 10} ${centerPositions.head.x + 40},${centerPositions.head.y + 50} ${centerPositions.head.x - 40},${centerPositions.head.y + 50}`}
            fill={getCenterFill("head")}
            stroke={getCenterStroke("head")}
            strokeWidth="2"
          />

          {/* Ajna Center - Triangle */}
          <polygon
            points={`${centerPositions.ajna.x},${centerPositions.ajna.y + 10} ${centerPositions.ajna.x + 40},${centerPositions.ajna.y + 50} ${centerPositions.ajna.x - 40},${centerPositions.ajna.y + 50}`}
            fill={getCenterFill("ajna")}
            stroke={getCenterStroke("ajna")}
            strokeWidth="2"
          />

          {/* Throat Center - Square */}
          <rect
            x={centerPositions.throat.x - 40}
            y={centerPositions.throat.y}
            width={centerPositions.throat.width}
            height={centerPositions.throat.height}
            fill={getCenterFill("throat")}
            stroke={getCenterStroke("throat")}
            strokeWidth="2"
          />

          {/* G Center - Diamond */}
          <polygon
            points={`${centerPositions.g.x},${centerPositions.g.y} ${centerPositions.g.x + 40},${centerPositions.g.y + 40} ${centerPositions.g.x},${centerPositions.g.y + 80} ${centerPositions.g.x - 40},${centerPositions.g.y + 40}`}
            fill={getCenterFill("g")}
            stroke={getCenterStroke("g")}
            strokeWidth="2"
          />

          {/* Heart/Ego Center - Triangle */}
          <polygon
            points={`${centerPositions.heart.x},${centerPositions.heart.y} ${centerPositions.heart.x + 35},${centerPositions.heart.y + 50} ${centerPositions.heart.x - 35},${centerPositions.heart.y + 50}`}
            fill={getCenterFill("heart")}
            stroke={getCenterStroke("heart")}
            strokeWidth="2"
          />

          {/* Sacral Center - Square */}
          <rect
            x={centerPositions.sacral.x - 40}
            y={centerPositions.sacral.y}
            width={centerPositions.sacral.width}
            height={centerPositions.sacral.height}
            fill={getCenterFill("sacral")}
            stroke={getCenterStroke("sacral")}
            strokeWidth="2"
          />

          {/* Spleen Center - Triangle */}
          <polygon
            points={`${centerPositions.spleen.x},${centerPositions.spleen.y} ${centerPositions.spleen.x + 35},${centerPositions.spleen.y + 50} ${centerPositions.spleen.x - 35},${centerPositions.spleen.y + 50}`}
            fill={getCenterFill("spleen")}
            stroke={getCenterStroke("spleen")}
            strokeWidth="2"
          />

          {/* Solar Plexus Center - Triangle */}
          <polygon
            points={`${centerPositions.solar.x},${centerPositions.solar.y} ${centerPositions.solar.x + 35},${centerPositions.solar.y + 50} ${centerPositions.solar.x - 35},${centerPositions.solar.y + 50}`}
            fill={getCenterFill("solar")}
            stroke={getCenterStroke("solar")}
            strokeWidth="2"
          />

          {/* Root Center - Square */}
          <rect
            x={centerPositions.root.x - 40}
            y={centerPositions.root.y}
            width={centerPositions.root.width}
            height={centerPositions.root.height}
            fill={getCenterFill("root")}
            stroke={getCenterStroke("root")}
            strokeWidth="2"
          />

          {/* Center Labels */}
          {Object.entries(centerPositions).map(([code, pos]) => {
            const center = centers.find((c) => c.code === code);
            if (!center) return null;
            return (
              <text
                key={code}
                x={pos.x}
                y={pos.y + pos.height + 15}
                textAnchor="middle"
                fontSize="10"
                fill="#2C3E50"
              >
                {center.name}
              </text>
            );
          })}
        </svg>
      </div>
      <div className="mt-4 flex flex-wrap justify-center gap-4 text-sm text-secondary">
        <span className="flex items-center gap-2">
          <span
            className="inline-block w-3 h-3 rounded-sm border"
            style={{ backgroundColor: FILL_BY_STATE.defined, borderColor: STROKE_BY_STATE.defined }}
          />
          {LABELS.defined}
        </span>
        <span className="flex items-center gap-2">
          <span
            className="inline-block w-3 h-3 rounded-sm border"
            style={{ backgroundColor: FILL_BY_STATE.unconscious, borderColor: STROKE_BY_STATE.unconscious }}
          />
          {LABELS.unconsciouslyDefined}
        </span>
        <span className="flex items-center gap-2">
          <span
            className="inline-block w-3 h-3 rounded-sm border"
            style={{ backgroundColor: FILL_BY_STATE.open, borderColor: STROKE_BY_STATE.open }}
          />
          {LABELS.open}
        </span>
      </div>
    </div>
  );
}
