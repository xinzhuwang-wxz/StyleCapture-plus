import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import type { Item, Ownership } from "../../api/client";
import { useSourceImage } from "./useSourceImage";

type ItemDetailProps = {
  item: Item | null;
  saving: boolean;
  onClose: () => void;
  onSave: (
    itemId: string,
    changes: {
      ownership: Ownership;
      corrections: Record<string, string>;
    }
  ) => void;
  onDeleteSource: (itemId: string) => void;
};

function DetailContent({
  item,
  saving,
  onClose,
  onSave,
  onDeleteSource
}: Omit<ItemDetailProps, "item"> & { item: Item }) {
  const imageUrl = useSourceImage(item.id, !item.source_available);
  const [ownership, setOwnership] = useState<Ownership>(item.ownership);
  const [category, setCategory] = useState(String(item.attributes.category?.value ?? ""));
  const [description, setDescription] = useState(
    String(item.attributes.description?.value ?? "")
  );
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    setOwnership(item.ownership);
    setCategory(String(item.attributes.category?.value ?? ""));
    setDescription(String(item.attributes.description?.value ?? ""));
    setConfirmingDelete(false);
  }, [item]);

  return (
    <motion.section
      className="detail-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="item-detail-title"
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ type: "spring", stiffness: 340, damping: 36 }}
    >
      <div className="detail-topbar">
        <button className="icon-button" type="button" aria-label="返回衣橱" onClick={onClose}>
          ‹
        </button>
        <strong id="item-detail-title">单品详情</strong>
        <span className="detail-topbar__spacer" />
      </div>

      <div className="detail-image">
        {imageUrl ? (
          <img src={imageUrl} alt={description || "衣橱单品原图"} />
        ) : (
          <div className="item-image-placeholder">
            <span>衣</span>
            <small>原图已删除或不可用</small>
          </div>
        )}
      </div>

      <div className="detail-content">
        <div className="detail-meta">
          <span>{item.source_kind === "camera" ? "拍照录入" : "相册录入"}</span>
          <span>{item.status === "ready" ? "已完成理解" : "仍可编辑"}</span>
        </div>

        <label className="form-field">
          <span>分类</span>
          <input
            value={category}
            maxLength={80}
            placeholder="例如：上装"
            onChange={(event) => setCategory(event.target.value)}
          />
        </label>
        <label className="form-field">
          <span>单品描述</span>
          <textarea
            value={description}
            maxLength={1000}
            rows={3}
            placeholder="补充你更准确的描述"
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>

        <div className="segmented-control" aria-label="衣服归属">
          <button
            type="button"
            className={ownership === "owned" ? "is-selected" : ""}
            onClick={() => setOwnership("owned")}
          >
            我的衣服
          </button>
          <button
            type="button"
            className={ownership === "inspiration" ? "is-selected" : ""}
            onClick={() => setOwnership("inspiration")}
          >
            穿搭灵感
          </button>
        </div>

        <button
          className="primary-action"
          type="button"
          disabled={saving}
          onClick={() =>
            onSave(item.id, {
              ownership,
              corrections: {
                ...(category.trim() ? { category: category.trim() } : {}),
                ...(description.trim() ? { description: description.trim() } : {})
              }
            })
          }
        >
          {saving ? "保存中…" : "保存修改"}
        </button>
        {!item.source_available ? (
          <p className="privacy-note">原图已删除，保留的标签和描述仍可继续编辑。</p>
        ) : confirmingDelete ? (
          <div className="delete-confirmation" role="alert">
            <p>删除后原图无法恢复，但分类、描述和归属仍会保留。</p>
            <div>
              <button type="button" onClick={() => setConfirmingDelete(false)}>
                保留原图
              </button>
              <button type="button" onClick={() => onDeleteSource(item.id)}>
                确认删除原图
              </button>
            </div>
          </div>
        ) : (
          <button
            className="danger-link"
            type="button"
            onClick={() => setConfirmingDelete(true)}
          >
            删除原图
          </button>
        )}
      </div>
    </motion.section>
  );
}

export function ItemDetail(props: ItemDetailProps) {
  return (
    <AnimatePresence>
      {props.item ? (
        <div className="detail-layer">
          <DetailContent {...props} item={props.item} />
        </div>
      ) : null}
    </AnimatePresence>
  );
}
