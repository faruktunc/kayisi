import csv
import io


def run_table_csv(rows: list[dict], factor_columns: list[tuple[str, str]], response_columns: list[str]) -> str:
    """Laboratuvar için deney tablosu: faktörler dolu, yanıt sütunları boş.
    Türkçe Excel ile uyum için ';' ayırıcı kullanılır."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Deney sırası", "Desen no", *[label for _, label in factor_columns], *response_columns])
    for row in rows:
        writer.writerow([row["run_order"], row["standard_order"],
                         *[str(row["factors"][key]).replace(".", ",") for key, _ in factor_columns],
                         *[""] * len(response_columns)])
    return "﻿" + buf.getvalue()
