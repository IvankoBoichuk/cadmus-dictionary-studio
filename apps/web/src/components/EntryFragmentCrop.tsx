import { useState, type SyntheticEvent } from "react";

import { dictionaryPageImageUrl, type EntryFragmentResponse } from "../api";

type Size = { width: number; height: number };
type Box = { x: number; y: number; width: number; height: number };

const CROP_DISPLAY_WIDTH = 480;
const CROP_CONTEXT_PADDING_RATIO = 0.2;
const CROP_MIN_PADDING = 40;

function fragmentBoxes(fragment: EntryFragmentResponse): Box[] {
  const boxes: Box[] = [
    { x: fragment.x, y: fragment.y, width: fragment.width, height: fragment.height },
  ];
  if (
    fragment.x2 != null &&
    fragment.y2 != null &&
    fragment.width2 != null &&
    fragment.height2 != null
  ) {
    boxes.push({
      x: fragment.x2,
      y: fragment.y2,
      width: fragment.width2,
      height: fragment.height2,
    });
  }
  return boxes;
}

/** BH-148: a zoomed-in crop of the source page around one entry fragment,
 * so an editor can see exactly how the article was printed while filling
 * in its fields. */
export function EntryFragmentCrop({
  dictionaryId,
  fragment,
}: {
  dictionaryId: string;
  fragment: EntryFragmentResponse;
}) {
  const [naturalSize, setNaturalSize] = useState<Size | null>(null);

  if (fragment.page_number == null) {
    return (
      <p className="lede">
        Не вдалося визначити сторінку джерела для цього фрагмента.
      </p>
    );
  }

  const boxes = fragmentBoxes(fragment);
  const minX = Math.min(...boxes.map((box) => box.x));
  const minY = Math.min(...boxes.map((box) => box.y));
  const maxX = Math.max(...boxes.map((box) => box.x + box.width));
  const maxY = Math.max(...boxes.map((box) => box.y + box.height));
  const padding =
    Math.max(maxX - minX, maxY - minY) * CROP_CONTEXT_PADDING_RATIO || CROP_MIN_PADDING;

  const cropX = Math.max(0, minX - padding);
  const cropY = Math.max(0, minY - padding);
  const cropWidth = maxX - minX + padding * 2;
  const cropHeight = maxY - minY + padding * 2;
  const scale = cropWidth > 0 ? CROP_DISPLAY_WIDTH / cropWidth : 1;
  const displayHeight = cropHeight * scale;

  const handleLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    setNaturalSize({ width: image.naturalWidth, height: image.naturalHeight });
  };

  return (
    <div
      className="entry-fragment-crop"
      style={{ width: CROP_DISPLAY_WIDTH, height: displayHeight }}
    >
      <img
        className="entry-fragment-crop-image"
        src={dictionaryPageImageUrl(dictionaryId, fragment.page_number)}
        alt={`Скан сторінки ${fragment.page_number}: «${fragment.recognized_text}»`}
        draggable={false}
        onLoad={handleLoad}
        style={{
          left: -cropX * scale,
          top: -cropY * scale,
          width: naturalSize ? naturalSize.width * scale : undefined,
          height: naturalSize ? naturalSize.height * scale : undefined,
        }}
      />
      {boxes.map((box) => (
        <div
          key={`${box.x}-${box.y}`}
          className="entry-fragment-crop-box"
          style={{
            left: (box.x - cropX) * scale,
            top: (box.y - cropY) * scale,
            width: box.width * scale,
            height: box.height * scale,
          }}
        />
      ))}
    </div>
  );
}
