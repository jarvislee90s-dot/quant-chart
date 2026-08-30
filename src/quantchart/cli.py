"""chartflow run config.yaml -o out.png [--html out.html]"""
import os
import shutil
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
@click.option("--project", "project", default=None,
              help="项目文件夹：一图一文件夹归档（config 快照/PNG/HTML/refs/compare）；"
                   "-o/--html 显式给定时优先于派生路径，也可由 YAML 顶层 project 字段指定")
def run(config, output, html, title, project):
    from .core.config import load_config
    from .core.pipeline import run_pipeline
    cfg = load_config(config)
    project = project or cfg.get("project")
    if project:
        _ensure_parent(f"{project}/chart.png")
        if output == "out.png":                 # 未显式指定 -o → 派生到项目文件夹
            output = f"{project}/chart.png"
        if html is None:
            html = f"{project}/chart.html"
    fig, rep = run_pipeline(cfg, title=title or cfg.get("title", ""))
    _ensure_parent(output)
    fig.write_image(output, width=1600, height=900)
    click.echo(f"PNG  -> {output}")
    if html:
        _ensure_parent(html)
        fig.write_html(html, include_plotlyjs="cdn")
        click.echo(f"HTML -> {html}")
    if project:
        shutil.copyfile(config, f"{project}/config.yaml")   # 配置快照归档（configs/ 仍为权威源）
        click.echo(f"项目 -> {project}（config 快照已归档）")
    click.echo(rep.footnote())


if __name__ == "__main__":
    main()
