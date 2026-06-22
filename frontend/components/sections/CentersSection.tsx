import { Center } from "@/types/chart";
import { LABELS } from "@/utils/constants";

interface CentersSectionProps {
  centers: Center[];
}

export default function CentersSection({ centers }: CentersSectionProps) {
  const defined = centers.filter((c) => c.definitionType === "defined");
  const unconscious = centers.filter((c) => c.definitionType === "unconscious");
  const open = centers.filter((c) => c.definitionType === "open");

  return (
    <div className="p-6 bg-white rounded-lg shadow-md">
      <h3 className="text-xl font-semibold text-primary mb-4">{LABELS.yourCenters}</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <h4 className="font-medium text-primary mb-2">{LABELS.defined}</h4>
          <ul className="space-y-1">
            {defined.map((center) => (
              <li key={center.code} className="text-secondary">
                {center.name}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="font-medium text-primary mb-2">{LABELS.unconsciouslyDefined}</h4>
          <ul className="space-y-1">
            {unconscious.map((center) => (
              <li key={center.code} className="text-secondary">
                {center.name}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="font-medium text-primary mb-2">{LABELS.open}</h4>
          <ul className="space-y-1">
            {open.map((center) => (
              <li key={center.code} className="text-secondary">
                {center.name}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
