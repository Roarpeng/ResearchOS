use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn export_script_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../scripts/export-pdf.mjs")
}

#[tauri::command]
pub async fn pick_export_pdf_path(
    app: tauri::AppHandle,
    default_name: Option<String>,
) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;

    let file_name = default_name.unwrap_or_else(|| "Untitled.pdf".to_string());
    let path = app
        .dialog()
        .file()
        .add_filter("PDF Document", &["pdf"])
        .set_file_name(&file_name)
        .blocking_save_file();

    Ok(path.and_then(|file| {
        file.into_path()
            .ok()
            .map(|selected| selected.to_string_lossy().into_owned())
    }))
}

#[tauri::command]
pub async fn pick_export_zip_path(
    app: tauri::AppHandle,
    default_name: Option<String>,
) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;

    let file_name = default_name.unwrap_or_else(|| "Untitled.zip".to_string());
    let path = app
        .dialog()
        .file()
        .add_filter("ZIP Archive", &["zip"])
        .set_file_name(&file_name)
        .blocking_save_file();

    Ok(path.and_then(|file| {
        file.into_path()
            .ok()
            .map(|selected| selected.to_string_lossy().into_owned())
    }))
}

#[tauri::command]
pub async fn export_pdf(html: String, output_path: String) -> Result<(), String> {
    let output = Path::new(&output_path);
    if let Some(parent) = output.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Failed to create output directories: {error}"))?;
    }

    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_nanos();
    let temp_dir = std::env::temp_dir().join(format!("paperhelp-export-{nanos}"));
    fs::create_dir_all(&temp_dir)
        .map_err(|error| format!("Failed to create temp dir: {error}"))?;

    let html_path = temp_dir.join("document.html");
    fs::write(&html_path, html.as_bytes())
        .map_err(|error| format!("Failed to write HTML temp file: {error}"))?;

    let script_path = export_script_path();
    if !script_path.exists() {
        let _ = fs::remove_dir_all(&temp_dir);
        return Err(format!(
            "PDF export script not found at {}",
            script_path.display()
        ));
    }

    let result = Command::new("node")
        .arg(&script_path)
        .arg(&html_path)
        .arg(output)
        .output()
        .map_err(|error| format!("Failed to run Node PDF exporter: {error}"));

    let _ = fs::remove_dir_all(&temp_dir);

    let output = result?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        let detail = if stderr.trim().is_empty() {
            stdout.trim().to_string()
        } else {
            stderr.trim().to_string()
        };
        return Err(if detail.is_empty() {
            "PDF export failed".to_string()
        } else {
            detail
        });
    }

    Ok(())
}
