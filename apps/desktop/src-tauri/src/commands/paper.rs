use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

#[tauri::command]
pub async fn pick_save_paper_path(
    app: tauri::AppHandle,
    default_name: Option<String>,
) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;

    let file_name = default_name.unwrap_or_else(|| "Untitled.paper".to_string());
    let path = app
        .dialog()
        .file()
        .add_filter("PaperHelp Document", &["paper"])
        .set_file_name(&file_name)
        .blocking_save_file();

    Ok(path.and_then(|file| {
        file.into_path()
            .ok()
            .map(|selected| selected.to_string_lossy().into_owned())
    }))
}

#[tauri::command]
pub async fn pick_open_paper_path(app: tauri::AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;

    let path = app
        .dialog()
        .file()
        .add_filter("PaperHelp Document", &["paper"])
        .set_title("Open PaperHelp document")
        .blocking_pick_file();

    Ok(path.and_then(|file| {
        file.into_path()
            .ok()
            .map(|selected| selected.to_string_lossy().into_owned())
    }))
}

#[tauri::command]
pub async fn write_binary_file(path: String, data: Vec<u8>) -> Result<(), String> {
    let target = Path::new(&path);
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent).map_err(|error| format!("Failed to create directories: {error}"))?;
    }

    fs::write(target, data).map_err(|error| format!("Failed to write file: {error}"))
}

#[tauri::command]
pub async fn read_binary_file(path: String) -> Result<Vec<u8>, String> {
    fs::read(&path).map_err(|error| format!("Failed to read file: {error}"))
}

#[tauri::command]
pub async fn copy_file(src: String, dest: String) -> Result<(), String> {
    let destination = Path::new(&dest);
    if let Some(parent) = destination.parent() {
        fs::create_dir_all(parent).map_err(|error| format!("Failed to create directories: {error}"))?;
    }

    fs::copy(&src, destination).map_err(|error| format!("Failed to copy file: {error}"))?;
    Ok(())
}

#[tauri::command]
pub async fn create_temp_dir(prefix: Option<String>) -> Result<String, String> {
    let base = std::env::temp_dir();
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_nanos();
    let dir_name = format!("{}-{}", prefix.unwrap_or_else(|| "paperhelp".to_string()), nanos);
    let path: PathBuf = base.join(dir_name);
    fs::create_dir_all(&path).map_err(|error| format!("Failed to create temp dir: {error}"))?;
    Ok(path.to_string_lossy().into_owned())
}

#[tauri::command]
pub async fn remove_path(path: String) -> Result<(), String> {
    let target = Path::new(&path);
    if !target.exists() {
        return Ok(());
    }

    if target.is_dir() {
        fs::remove_dir_all(target).map_err(|error| format!("Failed to remove directory: {error}"))
    } else {
        fs::remove_file(target).map_err(|error| format!("Failed to remove file: {error}"))
    }
}

#[tauri::command]
pub async fn list_files(directory: String) -> Result<Vec<String>, String> {
    let entries = fs::read_dir(&directory)
        .map_err(|error| format!("Failed to read directory: {error}"))?;

    let mut files = Vec::new();
    for entry in entries {
        let entry = entry.map_err(|error| error.to_string())?;
        let path = entry.path();
        if path.is_file() {
            if let Some(name) = path.file_name().and_then(|value| value.to_str()) {
                files.push(name.to_string());
            }
        }
    }

    Ok(files)
}
