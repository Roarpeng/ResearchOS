mod commands;

use commands::asset::{pick_image_files, read_image_asset};
use commands::export::{export_pdf, pick_export_pdf_path, pick_export_zip_path};
use commands::paper::{
    copy_file, create_temp_dir, get_app_data_dir, list_files, pick_open_paper_path,
    pick_save_paper_path, read_binary_file, remove_path, write_binary_file,
};

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_sql::Builder::default().build())
        .invoke_handler(tauri::generate_handler![
            greet,
            pick_image_files,
            read_image_asset,
            pick_save_paper_path,
            pick_open_paper_path,
            pick_export_pdf_path,
            pick_export_zip_path,
            export_pdf,
            write_binary_file,
            read_binary_file,
            copy_file,
            create_temp_dir,
            get_app_data_dir,
            remove_path,
            list_files
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
