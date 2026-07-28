import { Component, type ReactNode } from "react";

type ScreenBoundaryProps = {
  children: ReactNode;
};

type ScreenBoundaryState = {
  failed: boolean;
};

/**
 * 一屏崩了只让这一屏崩。
 *
 * 这些屏是懒加载的，分块请求失败（网络抖动、正好赶上重新部署、开发时依赖
 * 缓存过期）会一路冒到根节点，整页变白，而且刷新也不一定能好——上次打开的
 * 详情会被恢复出来，于是再崩一次。真机上遇到过。
 *
 * 出错时给一个「重新加载」而不是白屏：分块加载失败是一次性的，重来一次
 * 通常就好了。
 */
export class ScreenBoundary extends Component<
  ScreenBoundaryProps,
  ScreenBoundaryState
> {
  state: ScreenBoundaryState = { failed: false };

  static getDerivedStateFromError(): ScreenBoundaryState {
    return { failed: true };
  }

  /**
   * 直接刷新常常还是崩：上次打开的详情会被 sessionStorage 恢复出来，
   * 于是又走进同一条路。恢复前先把这些「会复发」的状态清掉，
   * 让用户落回首页而不是再白一次。
   */
  private recover = () => {
    try {
      window.sessionStorage.removeItem("stylecapture:selected-look:v1");
    } catch {
      // 隐私模式下取不到 sessionStorage；那就直接刷新，不因为清理失败卡住。
    }
    window.location.reload();
  };

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="screen-boundary" role="alert">
        <p>这个页面没能加载出来。</p>
        <button type="button" onClick={this.recover}>
          重新加载
        </button>
      </div>
    );
  }
}
