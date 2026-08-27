"""chartflow run config.yaml -o out.png [--html out.html]"""
import os
import sys

import click


@click.group()
def main():
    pass


def _ensure_parent(path: str):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)


@main.command()
@click.argument("config", type=click.Path(exists=True))
@click.option("-o", "--output", default="out.png", help="输出PNG路径")
@click.option("--html", "html", default=None, help="同时输出交互HTML路径")
@click.option("--title", default=None, help="覆盖图表标题")
def run(config, output, html, title):
    from .core.config import load_config
    from .core.pipeline import run_pipeline
    cfg = load_config(config)
    fig, rep = run_pipeline(cfg, title=title or cfg.get("title", ""))
    _ensure_parent(output)
    fig.write_image(output, width=1600, height=900)
    click.echo(f"PNG  -> {output}")
    if html:
        _ensure_parent(html)
        fig.write_html(html, include_plotlyjs="cdn")
        click.echo(f"HTML -> {html}")
    click.echo(rep.footnote())


if __name__ == "__main__":
    main()
