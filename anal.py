import os
import re
import subprocess
import datetime

# --- CONFIGURAZIONE ---

# Cartelle da ignorare durante l'analisi
DIRECTORIES_TO_IGNORE = {
    '__pycache__',
    '.git',
    '.vscode',
    'venv',
    '.idea',
    'node_modules'
}

# Estensioni dei file da analizzare per segreti e encoding
FILE_EXTENSIONS_TO_SCAN = (
    '.py', '.html', '.css', '.js', '.json', '.yaml', '.yml', '.md', '.txt'
)

# Nome del file di log in output
LOG_FILE_NAME = 'analysis_log.txt'

# Pattern Regex per trovare potenziali segreti
SECRET_PATTERNS = {
    'API Key': re.compile(r'(api_key|secret_key|password|token)[\s_]*=[\s_]*["\'][A-Za-z0-9_./-]{16,}["\']', re.IGNORECASE),
    'Generic Secret': re.compile(r'["\'][A-Za-z0-9+/=]{20,}["\']'), # Stringhe lunghe e casuali
}

# Pattern Regex per trovare caratteri di encoding errati
ENCODING_ERROR_PATTERN = re.compile(r'[ÃâÂ]')

# --- FUNZIONI DI ANALISI ---

def run_external_tool(tool_command, tool_name, project_path, log_file):
    """
    Esegue uno strumento esterno come subprocess e scrive il suo output nel file di log.
    """
    log_file.write(f"\n--- INIZIO REPORT DI {tool_name.upper()} ---\n\n")
    print(f"[*] Esecuzione di {tool_name} in corso...")
    try:
        # Esegue il comando nella cartella del progetto
        result = subprocess.run(
            tool_command,
            cwd=project_path,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        output = result.stdout if result.stdout else "(Nessun output)"
        log_file.write(output)

        if result.stderr:
            log_file.write("\n--- ERRORI DELLO STRUMENTO ---\n")
            log_file.write(result.stderr)
            
    except FileNotFoundError:
        error_msg = f"ERRORE: Comando '{tool_command[0]}' non trovato. Assicurati che {tool_name} sia installato e nel PATH.\n"
        log_file.write(error_msg)
        print(f"[!] {error_msg}")
    except Exception as e:
        error_msg = f"ERRORE inaspettato durante l'esecuzione di {tool_name}: {e}\n"
        log_file.write(error_msg)
        print(f"[!] {error_msg}")
        
    log_file.write(f"\n--- FINE REPORT DI {tool_name.upper()} ---\n")
    print(f"[*] Esecuzione di {tool_name} completata.")


def analyze_files_for_custom_issues(project_path, log_file):
    """
    Scorre i file del progetto per controlli personalizzati (segreti e encoding).
    """
    log_file.write(f"--- INIZIO CONTROLLI PERSONALIZZATI (SEGRETI & ENCODING) ---\n\n")
    print("[*] Esecuzione dei controlli personalizzati (segreti, encoding)...")
    
    found_issues = False
    for root, dirs, files in os.walk(project_path):
        # Esclude le cartelle da ignorare
        dirs[:] = [d for d in dirs if d not in DIRECTORIES_TO_IGNORE]
        
        for filename in files:
            if not filename.endswith(FILE_EXTENSIONS_TO_SCAN):
                continue

            file_path = os.path.join(root, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        # Controllo Segreti
                        for name, pattern in SECRET_PATTERNS.items():
                            if pattern.search(line):
                                log_file.write(f"[SEGRETO TROVATO] File: {file_path}, Riga: {line_num} ({name})\n")
                                found_issues = True
                        
                        # Controllo Encoding
                        if ENCODING_ERROR_PATTERN.search(line):
                            log_file.write(f"[ENCODING ERRATO] File: {file_path}, Riga: {line_num}\n")
                            found_issues = True
                            
            except UnicodeDecodeError:
                log_file.write(f"[ERRORE DI LETTURA] Impossibile leggere il file con encoding UTF-8: {file_path}\n")
                found_issues = True
            except Exception as e:
                log_file.write(f"[ERRORE INASPETTATO] Durante la lettura del file {file_path}: {e}\n")
                found_issues = True

    if not found_issues:
        log_file.write("Nessun problema trovato durante i controlli personalizzati.\n")

    log_file.write(f"\n--- FINE CONTROLLI PERSONALIZZATI ---\n")
    print("[*] Controlli personalizzati completati.")

# --- FUNZIONE PRINCIPALE ---

def main():
    """
    Funzione principale che orchestra l'analisi.
    """
    print("--- Script di Analisi Codice ---")
    project_path = input("Inserisci il percorso completo della cartella del progetto da analizzare: ").strip()

    if not os.path.isdir(project_path):
        print(f"[!] Errore: Il percorso '{project_path}' non è una cartella valida.")
        return

    with open(LOG_FILE_NAME, 'w', encoding='utf-8') as log_file:
        log_file.write(f"Report di Analisi per il progetto: {project_path}\n")
        log_file.write(f"Data e Ora: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write("="*50 + "\n")

        # 1. Esecuzione controlli personalizzati
        analyze_files_for_custom_issues(project_path, log_file)
        
        # 2. Esecuzione di Flake8
        run_external_tool(['flake8', '.'], 'Flake8 (Stile e Bug)', project_path, log_file)

        # 3. Esecuzione di Radon
        run_external_tool(['radon', 'dup', '.', '-t', '10'], 'Radon (Codice Duplicato)', project_path, log_file)

    print("\n[+] Analisi completata!")
    print(f"I risultati sono stati salvati nel file: {os.path.abspath(LOG_FILE_NAME)}")


if __name__ == "__main__":
    main()
