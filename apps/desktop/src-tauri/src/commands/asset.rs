use base64::{engine::general_purpose::STANDARD, Engine as _};
use image::imageops::FilterType;
use image::{GenericImageView, ImageFormat};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fs;
use std::io::Cursor;
use std::path::Path;

const THUMBNAIL_MAX: u32 = 128;

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ReadImageAssetResult {
    pub path: String,
    pub hash: String,
    pub width: u32,
    pub height: u32,
    pub mime: String,
    pub thumbnail: String,
}

fn mime_from_path(path: &Path) -> &'static str {
    match path
        .extension()
        .and_then(|ext| ext.to_str())
        .map(|ext| ext.to_ascii_lowercase())
        .as_deref()
    {
        Some("png") => "image/png",
        Some("jpg" | "jpeg") => "image/jpeg",
        Some("tiff" | "tif") => "image/tiff",
        Some("webp") => "image/webp",
        _ => "application/octet-stream",
    }
}

fn compute_sha256(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}

fn generate_thumbnail(data: &[u8]) -> Result<String, String> {
    let img = image::load_from_memory(data).map_err(|error| error.to_string())?;
    let (width, height) = img.dimensions();
    let thumb = if width > THUMBNAIL_MAX || height > THUMBNAIL_MAX {
        img.resize(THUMBNAIL_MAX, THUMBNAIL_MAX, FilterType::Lanczos3)
    } else {
        img
    };

    let mut buf = Vec::new();
    thumb
        .write_to(&mut Cursor::new(&mut buf), ImageFormat::Jpeg)
        .map_err(|error| error.to_string())?;

    Ok(format!(
        "data:image/jpeg;base64,{}",
        STANDARD.encode(buf)
    ))
}

#[tauri::command]
pub async fn pick_image_files(app: tauri::AppHandle) -> Result<Vec<String>, String> {
    use tauri_plugin_dialog::DialogExt;

    let files = app
        .dialog()
        .file()
        .add_filter("Images", &["png", "jpg", "jpeg", "tiff", "tif", "webp"])
        .set_title("Select images")
        .blocking_pick_files();

    match files {
        Some(paths) => Ok(paths
            .into_iter()
            .filter_map(|file| {
                file.into_path()
                    .ok()
                    .map(|path| path.to_string_lossy().into_owned())
            })
            .collect()),
        None => Ok(vec![]),
    }
}

#[tauri::command]
pub async fn read_image_from_bytes(
    app: tauri::AppHandle,
    data: Vec<u8>,
    extension: Option<String>,
) -> Result<ReadImageAssetResult, String> {
    use tauri::Manager;

    let hash = compute_sha256(&data);
    let img = image::load_from_memory(&data).map_err(|error| format!("Invalid image: {error}"))?;
    let (width, height) = img.dimensions();

    let ext = extension.unwrap_or_else(|| "png".to_string());
    let mime = match ext.to_ascii_lowercase().as_str() {
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "gif" => "image/gif",
        "webp" => "image/webp",
        "tiff" | "tif" => "image/tiff",
        _ => "image/png",
    }
    .to_string();

    let app_dir = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("Failed to resolve app data dir: {error}"))?;
    let import_dir = app_dir.join("imported");
    fs::create_dir_all(&import_dir)
        .map_err(|error| format!("Failed to create import dir: {error}"))?;

    let file_path = import_dir.join(format!("{hash}.{ext}"));
    if !file_path.exists() {
        fs::write(&file_path, &data)
            .map_err(|error| format!("Failed to write image: {error}"))?;
    }

    let path = file_path.to_string_lossy().into_owned();
    let thumbnail = generate_thumbnail(&data)?;

    Ok(ReadImageAssetResult {
        path,
        hash,
        width,
        height,
        mime,
        thumbnail,
    })
}

#[tauri::command]
pub async fn read_image_asset(path: String) -> Result<ReadImageAssetResult, String> {
    let path_buf = Path::new(&path);
    let data = fs::read(path_buf).map_err(|error| format!("Failed to read file: {error}"))?;
    let hash = compute_sha256(&data);
    let img = image::load_from_memory(&data).map_err(|error| format!("Invalid image: {error}"))?;
    let (width, height) = img.dimensions();
    let mime = mime_from_path(path_buf).to_string();
    let thumbnail = generate_thumbnail(&data)?;

    Ok(ReadImageAssetResult {
        path,
        hash,
        width,
        height,
        mime,
        thumbnail,
    })
}
