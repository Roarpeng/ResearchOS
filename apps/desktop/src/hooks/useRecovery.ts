import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  checkRecoveryAvailable,
  clearRecoverySession,
  getRecoveryPaths,
  recoverPaperFromMarker,
  removeRecoveryArtifacts,
  type RecoveryMarker,
  type SyncContext,
} from "@paperhelp/db";
import { getAppDataDir, paperFileIO } from "../services/paperIo";

export const RECOVERY_DIALOG_ID = "paper-recovery";

export function useRecoveryPrompt(syncContext: SyncContext) {
  const navigate = useNavigate();
  const [marker, setMarker] = useState<RecoveryMarker | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const appDataDir = await getAppDataDir();
        const pending = await checkRecoveryAvailable(paperFileIO, appDataDir);
        if (!cancelled && pending) {
          setMarker(pending);
        }
      } catch (error) {
        console.error("Failed to check recovery state", error);
      } finally {
        if (!cancelled) {
          setChecked(true);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const dismissRecovery = useCallback(async () => {
    try {
      const appDataDir = await getAppDataDir();
      const paths = getRecoveryPaths(appDataDir);
      await removeRecoveryArtifacts(paperFileIO, paths);
    } catch (error) {
      console.error("Failed to discard recovery data", error);
    } finally {
      setMarker(null);
    }
  }, []);

  const acceptRecovery = useCallback(async () => {
    if (!marker) {
      return;
    }

    try {
      const loaded = await recoverPaperFromMarker({
        fileIO: paperFileIO,
        syncContext,
        marker,
      });

      if (loaded) {
        navigate(`/editor/${loaded.documentId}`);
      }
    } catch (error) {
      console.error("Failed to recover document", error);
    } finally {
      setMarker(null);
    }
  }, [marker, navigate, syncContext]);

  return {
    checked,
    marker,
    acceptRecovery,
    dismissRecovery,
  };
}

export async function finalizeSessionOnClose(
  flushAutosave: () => Promise<void>,
): Promise<void> {
  await flushAutosave();

  try {
    const appDataDir = await getAppDataDir();
    const paths = getRecoveryPaths(appDataDir);
    await clearRecoverySession(paperFileIO, paths);
  } catch (error) {
    console.error("Failed to finalize session on close", error);
  }
}
