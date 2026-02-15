"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Check, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SessionSlot } from "@/lib/types";

interface SessionCardProps {
  session: SessionSlot;
  onMarkDone?: () => void;
  onMarkSkipped?: () => void;
}

/** Formatta il session_id in modo leggibile: replace _ con spazi, capitalize */
function formatSessionName(sessionId: string): string {
  return sessionId
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Mappa slot a etichetta italiana */
function formatSlot(slot: string): string {
  const slotMap: Record<string, string> = {
    morning: "Mattina",
    afternoon: "Pomeriggio",
    evening: "Sera",
  };
  return slotMap[slot] ?? slot;
}

export function SessionCard({
  session,
  onMarkDone,
  onMarkSkipped,
}: SessionCardProps) {
  const [expanded, setExpanded] = useState(false);

  const isHard = session.tags?.hard === true;
  const isFinger = session.tags?.finger === true;

  return (
    <Card className="gap-0 py-0 overflow-hidden">
      {/* Header — cliccabile per espandere */}
      <CardHeader
        className="cursor-pointer select-none py-3"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm">
            {formatSessionName(session.session_id)}
          </CardTitle>
          {expanded ? (
            <ChevronUp className="size-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
          )}
        </div>

        {/* Badge riga */}
        <div className="flex flex-wrap items-center gap-1.5 mt-1">
          <Badge variant="secondary" className="text-[10px]">
            {session.location === "home" ? "Casa" : session.location}
          </Badge>
          <Badge variant="outline" className="text-[10px]">
            {formatSlot(session.slot)}
          </Badge>
          {isHard && (
            <Badge className="bg-red-500 text-white text-[10px]">
              Intensa
            </Badge>
          )}
          {isFinger && (
            <Badge className="bg-orange-500 text-white text-[10px]">
              Dita
            </Badge>
          )}
        </div>
      </CardHeader>

      {/* Contenuto espanso */}
      {expanded && (
        <CardContent className="pt-0 pb-3 space-y-3">
          {/* Placeholder lista esercizi */}
          <div className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
            Esercizi non ancora caricati
          </div>

          {/* Pulsanti azione */}
          <div className="flex items-center gap-2">
            {onMarkDone && (
              <Button
                size="sm"
                variant="outline"
                className="text-green-600 border-green-300 hover:bg-green-50 dark:hover:bg-green-950"
                onClick={(e) => {
                  e.stopPropagation();
                  onMarkDone();
                }}
              >
                <Check className="size-4 mr-1" />
                Fatto
              </Button>
            )}
            {onMarkSkipped && (
              <Button
                size="sm"
                variant="outline"
                className="text-muted-foreground"
                onClick={(e) => {
                  e.stopPropagation();
                  onMarkSkipped();
                }}
              >
                <X className="size-4 mr-1" />
                Saltato
              </Button>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
