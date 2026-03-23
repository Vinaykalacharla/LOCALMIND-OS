# Cross Entropy vs MSE

## Context
These notes compare common loss functions for classification and regression tasks.

## Cross Entropy
- Designed for probabilistic classification outputs.
- Penalizes confident wrong predictions heavily.
- Works naturally with softmax/sigmoid outputs.
- Gives stronger gradients when predictions are poor.
- Usually converges faster for multi-class classification.

## Mean Squared Error (MSE)
- Standard for regression where outputs are continuous.
- Measures squared difference between prediction and target.
- For classification with one-hot labels, gradients can be weaker than cross entropy.
- More sensitive to outliers due to squaring.

## Practical Guidance
- Use **Cross Entropy** for classification problems.
- Use **MSE** for regression problems.
- In noisy regression settings, Huber loss can be a robust alternative.

## Example Weak Areas for Revision
- Deriving cross entropy gradients from softmax.
- Interpreting calibration vs accuracy.
- Diagnosing underfitting from loss curves.

