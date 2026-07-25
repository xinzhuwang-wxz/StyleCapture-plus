import { useEffect, useRef } from "react";

const cutoutWidth = 160;
const cutoutHeight = 214;

function isBackdrop(red: number, green: number, blue: number, alpha: number) {
  if (alpha < 20) return true;
  const maximum = Math.max(red, green, blue);
  const minimum = Math.min(red, green, blue);
  return (
    (red > 242 && green > 230 && blue > 230) ||
    (maximum > 232 && maximum - minimum < 30)
  );
}

function keepLargestOpaqueShape(imageData: ImageData) {
  const { data, width, height } = imageData;
  const labels = new Int32Array(width * height);
  labels.fill(-1);
  const queue = new Int32Array(width * height);
  const componentSizes: number[] = [];
  let component = 0;

  for (let index = 0; index < labels.length; index += 1) {
    if (labels[index] !== -1 || data[index * 4 + 3] === 0) continue;
    let start = 0;
    let end = 0;
    let size = 0;
    queue[end++] = index;
    labels[index] = component;
    while (start < end) {
      const current = queue[start++];
      size += 1;
      const x = current % width;
      const y = Math.floor(current / width);
      const neighbors = [
        x > 0 ? current - 1 : -1,
        x < width - 1 ? current + 1 : -1,
        y > 0 ? current - width : -1,
        y < height - 1 ? current + width : -1
      ];
      neighbors.forEach((neighbor) => {
        if (
          neighbor >= 0 &&
          labels[neighbor] === -1 &&
          data[neighbor * 4 + 3] !== 0
        ) {
          labels[neighbor] = component;
          queue[end++] = neighbor;
        }
      });
    }
    componentSizes.push(size);
    component += 1;
  }

  let largest = -1;
  let largestSize = 0;
  componentSizes.forEach((size, index) => {
    if (size > largestSize) {
      largest = index;
      largestSize = size;
    }
  });
  if (largest === -1) return;
  for (let index = 0; index < labels.length; index += 1) {
    if (labels[index] !== largest) data[index * 4 + 3] = 0;
  }
}

export function PixelGuest({ source }: { source: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    const image = new Image();
    image.onload = () => {
      canvas.width = cutoutWidth;
      canvas.height = cutoutHeight;
      context.imageSmoothingEnabled = false;
      const ratio = Math.min(
        cutoutWidth / image.naturalWidth,
        cutoutHeight / image.naturalHeight
      );
      const width = image.naturalWidth * ratio;
      const height = image.naturalHeight * ratio;
      context.drawImage(
        image,
        (cutoutWidth - width) / 2,
        (cutoutHeight - height) / 2,
        width,
        height
      );
      const imageData = context.getImageData(0, 0, cutoutWidth, cutoutHeight);
      for (let index = 0; index < imageData.data.length; index += 4) {
        if (
          isBackdrop(
            imageData.data[index],
            imageData.data[index + 1],
            imageData.data[index + 2],
            imageData.data[index + 3]
          )
        ) {
          imageData.data[index + 3] = 0;
        }
      }
      keepLargestOpaqueShape(imageData);
      context.putImageData(imageData, 0, 0);
    };
    image.src = source;
  }, [source]);

  return <canvas ref={canvasRef} aria-hidden="true" />;
}
