import argparse
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from llmops_lab.db.connectors import SyncDatabaseConnection
from llmops_lab.logging.logger import get_logger

logger = get_logger(__name__)


def apply_ddl(db: SyncDatabaseConnection, sql_file: Path):
    """
    Aplica um arquivo DDL no banco

    Args:
        db: Conexão com banco
        sql_file: Caminho do arquivo SQL
    """
    logger.info(f"Aplicando DDL: {sql_file.name}")

    try:
        with open(sql_file, encoding="utf-8") as f:
            sql = f.read()

        # Executa SQL completo de uma vez
        with db.engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()

        logger.info(f"OK {sql_file.name} aplicado com sucesso")

    except Exception as e:
        logger.error(f"ERRO ao aplicar {sql_file.name}: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Aplica DDLs no banco de dados")
    parser.add_argument(
        "--file",
        help="Arquivo SQL específico para aplicar",
        type=Path,
    )
    parser.add_argument(
        "--dir",
        help="Diretório com arquivos SQL (padrão: data-schemas/sql)",
        type=Path,
        default=Path("data-schemas/sql"),
    )

    args = parser.parse_args()

    # Inicializa conexão
    logger.info("Conectando ao banco de dados...")
    db = SyncDatabaseConnection()
    db.connect()

    try:
        if args.file:
            # Aplica arquivo específico
            if not args.file.exists():
                logger.error(f"Arquivo não encontrado: {args.file}")
                sys.exit(1)

            apply_ddl(db, args.file)
        else:
            # Aplica todos os arquivos do diretório em ordem
            if not args.dir.exists():
                logger.error(f"Diretório não encontrado: {args.dir}")
                sys.exit(1)

            sql_files = sorted(args.dir.glob("*.sql"))

            if not sql_files:
                logger.warning(f"Nenhum arquivo .sql encontrado em {args.dir}")
                sys.exit(0)

            logger.info(f"Encontrados {len(sql_files)} arquivos SQL")
            print()

            for sql_file in sql_files:
                apply_ddl(db, sql_file)
                print()

        logger.info("Todos os DDLs foram aplicados com sucesso!")

    except Exception as e:
        logger.error(f"Erro durante aplicação de DDLs: {e}")
        sys.exit(1)
    finally:
        db.disconnect()


if __name__ == "__main__":
    main()
