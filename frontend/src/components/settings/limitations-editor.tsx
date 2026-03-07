"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const AREAS = [
  { value: "elbow", label: "Elbow" },
  { value: "shoulder", label: "Shoulder" },
  { value: "wrist", label: "Wrist" },
  { value: "knee", label: "Knee" },
  { value: "back", label: "Back" },
];

const SIDES = [
  { value: "left", label: "Left" },
  { value: "right", label: "Right" },
  { value: "both", label: "Both" },
];

const SEVERITIES = [
  { value: "monitor", label: "Monitor", desc: "Mild discomfort — keep training but stay aware", color: "text-yellow-500" },
  { value: "active", label: "Active", desc: "Noticeable pain — reduce stress on this area", color: "text-orange-500" },
  { value: "severe", label: "Severe", desc: "Significant injury — avoid all exercises", color: "text-red-500" },
];

interface LimitationDetail {
  area: string;
  side: string;
  severity: string;
  notes?: string;
}

interface LimitationsData {
  active_flags?: string[];
  details?: LimitationDetail[];
}

interface LimitationsEditorProps {
  initialLimitations: LimitationsData;
  onSave: (limitations: LimitationsData) => void;
  onCancel: () => void;
}

function severityBadgeColor(severity: string) {
  if (severity === "monitor") return "bg-yellow-500/15 text-yellow-500 border-yellow-500/30";
  if (severity === "active") return "bg-orange-500/15 text-orange-500 border-orange-500/30";
  if (severity === "severe") return "bg-red-500/15 text-red-500 border-red-500/30";
  return "";
}

export function LimitationsEditor({ initialLimitations, onSave, onCancel }: LimitationsEditorProps) {
  const [details, setDetails] = useState<LimitationDetail[]>(
    () => JSON.parse(JSON.stringify(initialLimitations.details ?? [])),
  );

  const addLimitation = () => {
    setDetails([...details, { area: "", side: "", severity: "", notes: "" }]);
  };

  const removeLimitation = (index: number) => {
    setDetails(details.filter((_, i) => i !== index));
  };

  const setField = (index: number, field: keyof LimitationDetail, value: string) => {
    setDetails(details.map((d, i) => (i === index ? { ...d, [field]: value } : d)));
  };

  const isValid = details.every((d) => d.area && d.side && d.severity);

  const handleSave = () => {
    const activeFlags = details.map((d) => `${d.area}_${d.side}`);
    onSave({ active_flags: activeFlags, details });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Injuries & Limitations</CardTitle>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="text-xs" onClick={onCancel}>
              Cancel
            </Button>
            <Button size="sm" className="text-xs" disabled={!isValid} onClick={handleSave}>
              Save
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {details.length === 0 && (
          <p className="text-xs text-muted-foreground">No active limitations</p>
        )}

        {details.map((lim, index) => (
          <div key={index} className="space-y-3 rounded-lg border p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Limitation {index + 1}</p>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive text-xs h-7"
                onClick={() => removeLimitation(index)}
              >
                Remove
              </Button>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">Area</Label>
                <Select value={lim.area} onValueChange={(v) => setField(index, "area", v)}>
                  <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Area" /></SelectTrigger>
                  <SelectContent>
                    {AREAS.map((a) => (<SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Side</Label>
                <Select value={lim.side} onValueChange={(v) => setField(index, "side", v)}>
                  <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Side" /></SelectTrigger>
                  <SelectContent>
                    {SIDES.map((s) => (<SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Severity</Label>
                <Select value={lim.severity} onValueChange={(v) => setField(index, "severity", v)}>
                  <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Level" /></SelectTrigger>
                  <SelectContent>
                    {SEVERITIES.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        <div>
                          <span className="font-medium">{s.label}</span>
                          <p className="text-[10px] text-muted-foreground">{s.desc}</p>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Input
              value={lim.notes ?? ""}
              onChange={(e) => setField(index, "notes", e.target.value)}
              placeholder="Notes (optional)"
              className="h-8 text-xs"
            />
          </div>
        ))}

        <Button variant="outline" size="sm" className="w-full text-xs" onClick={addLimitation}>
          Add limitation
        </Button>
      </CardContent>
    </Card>
  );
}

/** Read-only summary for the settings page */
export function LimitationsSummary({
  limitations,
  onEdit,
}: {
  limitations: LimitationsData;
  onEdit: () => void;
}) {
  const details = limitations?.details ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Injuries & Limitations</CardTitle>
          <Button variant="outline" size="sm" className="text-xs" onClick={onEdit}>
            Edit
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {details.length === 0 ? (
          <p className="text-xs text-muted-foreground">No active limitations</p>
        ) : (
          <div className="space-y-2">
            {details.map((d, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="font-medium capitalize">{d.area}</span>
                <span className="text-xs text-muted-foreground">({d.side})</span>
                <Badge variant="outline" className={`text-[10px] ${severityBadgeColor(d.severity)}`}>
                  {d.severity}
                </Badge>
                {d.notes && (
                  <span className="text-xs text-muted-foreground truncate max-w-[150px]">{d.notes}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
