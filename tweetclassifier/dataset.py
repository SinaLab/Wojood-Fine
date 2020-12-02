import json
import torch
from torchtext.vocab import Vocab
from transformers import BertTokenizer
from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.rnn import pad_sequence
import itertools
from collections import Counter
from functools import partial
import logging

logger = logging.getLogger(__name__)


class TextTransform:
    def __init__(self, bert_model, max_seq_len=512):
        self.tokenizer = partial(
            BertTokenizer.from_pretrained(bert_model, do_lower_case=True).encode,
            max_length=max_seq_len,
            truncation=True,
        )

    def __call__(self, example):
        example["encoded_seq"] = torch.Tensor(self.tokenizer(example["tweet"])).long()
        return example


class LabelTransform:
    def __init__(self, labels, multi_label=False):
        self.label_vocab = Vocab(labels, specials=[])
        self.multi_label = multi_label

    def __call__(self, example):
        example["encoded_label"] = self.label_vocab.stoi[example["labels"][0]]
        return example


class TwitterDataset(Dataset):
    def __init__(self, examples, transform):
        self.transform = transform
        self.examples = examples

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, item):
        example = self.transform(self.examples[item])
        return example["encoded_seq"], example["encoded_label"]


def parse_json(data_paths):
    datasets = list()
    labels = list()

    for data_path in data_paths:
        with open(data_path, "r") as fh:
            dataset = json.load(fh)
            datasets.append(dataset)
            labels += itertools.chain(*[tweet["labels"] for tweet in dataset])
            logger.info("%d examples found in %s", len(dataset), data_path)

    labels = Counter(labels)
    logger.info("Labels %s", labels)

    return datasets, labels


def get_dataloaders(
    datasets, transform, batch_size=32, num_workers=0, shuffle=(True, True, False)
):
    dataloaders = list()

    for i, tweets in enumerate(datasets):
        dataset = TwitterDataset(tweets, transform)

        dataloader = DataLoader(
            dataset=dataset,
            shuffle=shuffle[i],
            batch_size=batch_size,
            num_workers=num_workers,
            collate_fn=batch_collate_fn,
        )

        logger.info("%s batches found", len(dataloader))
        dataloaders.append(dataloader)

    return dataloaders


def batch_collate_fn(batch):
    tweets, labels = zip(*batch)
    tweets = pad_sequence(tweets, batch_first=True, padding_value=0)
    return tweets, torch.Tensor(labels).long()
